"""Stage A: one locked, retried platform departure; identity purge is a later stage."""

import logging
from uuid import uuid4
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import APIException, AuthenticationFailed, PermissionDenied

from apps.accounts import reauthentication
from apps.accounts.account_deletion_blockers import blocker, collect
from apps.accounts.account_deletion_discovery import organization_ids, tenant_ids
from apps.accounts.models import User
from apps.audit import services as audit
from apps.backup.not_restored import TenantNotRestored
from apps.makerspaces.models import Makerspace, MakerspaceMembership, MembershipRequest
from apps.organizations.models import Organization
from apps.tenant_migration.gate_errors import SourceMigrationGateClosed
from apps.tenant_migration.gate_runtime import assert_write_allowed

logger = logging.getLogger(__name__)


class DeletionBlocked(APIException):
    status_code = 409

    def __init__(self, blockers):
        self.blockers = blockers
        if any(row["code"] == "superadmin" for row in blockers):
            self.status_code = 403
        super().__init__({"blockers": blockers})
        # APIException normally stringifies all nested leaves, including counts.
        self.detail = {"blockers": blockers}


class DeletionRetry(APIException):
    status_code = 503

    def __init__(self):
        super().__init__({"code": "deletion_retry", "detail": "Account participation changed. Try again."})


class _DiscoveryChanged(Exception):
    pass


def _gates(ids):
    gated = set()
    for pk in sorted(ids):
        try:
            # In an atomic block this retains the gate's shared advisory lock
            # through commit, including when the tenant is currently frozen.
            assert_write_allowed(pk)
        except (SourceMigrationGateClosed, TenantNotRestored):
            gated.add(pk)
    return gated


def preview(request):
    from apps.accounts.account_restore import restore_disclosure
    from apps.accounts.reauthentication_methods import methods
    with transaction.atomic():
        gated = _gates(tenant_ids(request.user))
        organizations = list(Organization.objects.select_for_update().filter(
            pk__in=organization_ids(request.user)).order_by("pk"))
        blockers = collect(request.user, gated=gated, organizations=organizations)
    required = False
    try:
        reauthentication.require_recent_reauth(request)
    except (PermissionDenied, AuthenticationFailed):
        required = True
    return {"deletable": not blockers, "blockers": blockers, **restore_disclosure(request.user),
            "reauth": {"required": required, "methods": methods(request.user)}}


def request_deletion(request):
    user = request.user
    if user.is_superuser or user.role == User.Role.SUPERADMIN:
        refused = [blocker("superadmin", detail="Superadmin accounts cannot request account deletion.")]
        _audit_refusal(user, refused)
        raise DeletionBlocked(refused)
    reauthentication.require_recent_reauth(request)
    for attempt in range(3):
        try:
            return _attempt(request)
        except _DiscoveryChanged:
            logger.info("account_deletion_discovery_changed", extra={"user_id": user.pk, "attempt": attempt + 1})
        except DeletionBlocked as exc:
            # The refusal must outlive rollback of the locked departure transaction.
            _audit_refusal(user, exc.blockers)
            raise
    raise DeletionRetry()


def _audit_refusal(user, blockers):
    audit.record(user, "account.deletion_refused", target=user,
                 meta={"blocker_codes": sorted({row["code"] for row in blockers})})


def _attempt(request):
    ids, org_ids = tenant_ids(request.user), organization_ids(request.user)
    with transaction.atomic():
        gated = _gates(ids)
        spaces = list(Makerspace.objects.select_for_update().filter(pk__in=ids).order_by("pk"))
        organizations = list(Organization.objects.select_for_update().filter(pk__in=org_ids).order_by("pk"))
        user = User.objects.select_for_update(no_key=True).get(pk=request.user.pk)
        if not tenant_ids(user).issubset(ids) or not organization_ids(user).issubset(org_ids):
            raise _DiscoveryChanged()
        request.user = user
        now = timezone.now()
        try:
            proof = reauthentication.current(request, lock=True)
        except AuthenticationFailed:
            # An in-flight account restriction can invalidate binding() while we
            # wait. Preserve its locked blocker and the durable refusal audit.
            blockers = collect(user, now=now, gated=gated, organizations=organizations)
            if blockers:
                raise DeletionBlocked(blockers)
            raise
        # current() validates the binding/version, but does not check auth_time.
        if proof is None or proof.auth_time is None or not now - reauthentication.WINDOW <= proof.auth_time <= now:
            raise reauthentication.RecentAuthenticationRequired()
        blockers = collect(user, now=now, gated=gated, organizations=organizations)
        if blockers:
            raise DeletionBlocked(blockers)
        _depart(user, spaces, organizations, now)
        user.is_active = False
        user.set_unusable_password()
        user.deletion_requested_at = now
        user.deletion_purge_after = now + timedelta(days=settings.ACCOUNT_DELETION_RETENTION_DAYS)
        from apps.makerspaces.secrets import encrypt_value
        from apps.accounts.apple_revocation import schedule_revocations
        user.deletion_email_ciphertext = encrypt_value(user.email) if user.email else ""
        user.deletion_username = "deleted_" + uuid4().hex
        user.save(update_fields=["is_active", "password", "deletion_requested_at", "deletion_purge_after",
                                 "deletion_email_ciphertext", "deletion_username"])
        schedule_revocations(user)
        audit.record(user, "account.deletion_requested", target=user,
                     meta={"purge_after": user.deletion_purge_after.isoformat()})
        return {"deleted_at": now, "purge_after": user.deletion_purge_after}


def _depart(user, spaces, organizations, now):
    from apps.accounts.account_deletion_credentials import revoke
    from apps.makerspaces.membership_admission_payments import close_admission
    from apps.makerspaces.membership_revocation import _revoke_locked
    from apps.organizations.services_governance import self_departure
    # Cancel as the applicant before membership revocation closes applications as
    # revoked; this is the exact service used by MemberAdmissionCancelView.
    for row in MembershipRequest.objects.select_for_update().filter(
        user=user, state__in=("requested", "invited", "awaiting_vouches"),
    ).order_by("makerspace_id", "pk"):
        close_admission(user, row)
    by_id = {space.pk: space for space in spaces}
    for membership in MakerspaceMembership.objects.select_for_update().filter(user=user).exclude(
        status="revoked",
    ).order_by("makerspace_id", "pk"):
        membership.renewal_cancelled_at = membership.renewal_cancelled_at or now
        _revoke_locked(user, membership, by_id[membership.makerspace_id], "Account deletion", self_leave=True)
    for organization in organizations:
        self_departure(organization, user=user)
    revoke(user, now)

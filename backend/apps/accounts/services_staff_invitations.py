"""Initial password invitations bound to an account and its exact authority."""
import secrets
from datetime import timedelta

from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.accounts import rbac
from apps.accounts.mfa_challenges import digest
from apps.accounts.models import StaffInvitation, User
from apps.accounts.staff_account_policy import require_authority
from apps.audit.services import record
from apps.makerspaces.models import Makerspace, MakerspaceMembership
from apps.makerspaces.platform import feature_enabled, module_enabled
from apps.makerspaces.secrets import encrypt_value
from apps.tenant_migration.gate_runtime import tenant_write


def scoped(actor):
    return rbac.scope_by_action(actor, rbac.Action.MANAGE_MAKERSPACE, StaffInvitation.objects.all())


def onboarding_available(space):
    return module_enabled(space, "email") and feature_enabled(space, "staff.invitations")


def authority(actor, space, role=None):
    if not onboarding_available(space):
        raise ValidationError({"detail": "Email onboarding is unavailable. Set an initial password instead."})
    require_authority(actor, space, roles=[role] if role else None)


def snapshot(account, membership):
    from apps.machines.member_scope_services import current_scope
    from apps.accounts.rbac_roles import membership_roles

    roles = membership_roles(membership)
    return {"role_snapshot": sorted(role.slug for role in roles),
            "machine_scope_snapshot": current_scope(membership),
            "credential_generation": account.credential_generation,
            "granted_actions": sorted(set().union(*(set(role.granted_actions) for role in roles)))}


def issue(actor, space, account, *, expires_in_days=7):
    """Caller owns the tenant transaction; delivery happens after it commits."""
    authority(actor, space)
    require_authority(actor, space, target=account)
    if (not account.is_active or account.has_usable_password() or not account.email
            or account.access_status != User.AccessStatus.ACTIVE):
        raise ValidationError({"detail": "Only active staff awaiting initial password setup may be invited."})
    if type(expires_in_days) is not int or not 1 <= expires_in_days <= 30:
        raise ValidationError({"expires_in_days": "Use 1 to 30 days."})
    membership = MakerspaceMembership.staff_tracks.get(user=account, makerspace=space, status="active")
    StaffInvitation.objects.filter(account=account, accepted_at__isnull=True,
                                   revoked_at__isnull=True).update(revoked_at=timezone.now())
    raw = secrets.token_urlsafe(32)
    row = StaffInvitation.objects.create(
        account=account, makerspace=space, role=membership.assigned_role,
        email_ciphertext=encrypt_value(account.email), token_digest=digest(raw),
        expires_at=timezone.now() + timedelta(days=expires_in_days), created_by=actor,
        **snapshot(account, membership),
    )
    record(actor, "staff.invitation_created", makerspace=space, target=row,
           meta={"role_id": row.role_id, "expires_at": row.expires_at.isoformat()})
    return row, raw


def create(actor, space_id, *, email, role_id, expires_in_days=7):
    raise ValidationError({"detail": "Create a separate staff account through staff-accounts first."})


def resend_account(actor, space_id, account_id):
    from apps.accounts.staff_account_policy import scoped_space, target_account

    with tenant_write(space_id):
        space, actor = scoped_space(actor, space_id, lock=True)
        list(StaffInvitation.objects.select_for_update().filter(account_id=account_id).order_by("pk"))
        account = target_account(space, account_id)
        account = User.objects.select_for_update().get(pk=account.pk)
        row, raw = issue(actor, space, account)
        record(actor, "staff.invitation_resent", makerspace=space, target=row)
    return row, raw


def mutate(actor, invitation, *, resend=False):
    if resend:
        with tenant_write(invitation.makerspace_id):
            from apps.accounts.staff_account_policy import scoped_space
            space, actor = scoped_space(actor, invitation.makerspace_id, lock=True)
            row = get_object_or_404(scoped(actor).select_for_update(), pk=invitation.pk, makerspace=space)
            if row.accepted_at or row.revoked_at or row.account_id is None:
                raise ValidationError({"detail": "This invitation cannot be resent. Use staff account onboarding."})
            return resend_account(actor, row.makerspace_id, row.account_id)
    with tenant_write(invitation.makerspace_id):
        space = Makerspace.objects.select_for_update(no_key=True).get(pk=invitation.makerspace_id)
        row = get_object_or_404(scoped(actor).select_for_update(), pk=invitation.pk, makerspace=space)
        actor = User.objects.get(pk=actor.pk)
        require_authority(actor, space, target=row.account)
        if row.accepted_at:
            raise ValidationError({"detail": "This invitation has already been accepted."})
        row.revoked_at = timezone.now()
        row.save(update_fields=["revoked_at"])
        record(actor, "staff.invitation_revoked", makerspace=space, target=row)
    return row, None

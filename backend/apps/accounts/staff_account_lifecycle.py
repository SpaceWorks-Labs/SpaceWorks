"""Revoke and restore a staff row; disable or re-enable an account from /control/ (Q8).

A Space Manager no longer sets passwords, reactivates accounts or resets factors (#66,
Q9): the person signs in with their own account, an MFA reset follows S-A's rule
(``mfa_reset``), and turning a whole ACCOUNT off is a superadmin ``/control/`` action
(``disable_account``) behind control step-up. Revoking a staff row ends only that staff
authority: the person's member features keep working, and their staff device grants in
that space are revoked (``services_staff_grants``).
"""

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.accounts.models import User
from apps.accounts.staff_account_policy import (
    check_staff_quota, protect_last_manager, require_authority, scoped_space, staff_write, target_row,
)
from apps.audit.services import record
from apps.makerspaces.models import MakerspaceMembership


def _reason(reason, default):
    if not isinstance(reason, str) or len(reason) > 200:
        raise ValidationError({"reason": "Use at most 200 characters."})
    return reason.strip() or default


def _revoke_row(actor, space, row, reason):
    from apps.accounts.services_staff_grants import revoke_staff_grants

    row.status, row.revoked_at, row.revoked_by = "revoked", timezone.now(), actor
    row.revocation_reason = reason
    row.save(update_fields=["status", "revoked_at", "revoked_by", "revocation_reason"])
    revoke_staff_grants(row.user, space.pk, reason="staff_role.revoked", actor=actor)
    record(actor, "staff_role.revoked", makerspace=space, target=row.user,
           meta={"membership_id": row.pk, "reason": reason})


def revoke(actor, space_id, membership_id, *, reason=""):
    reason = _reason(reason, "Staff role revoked")
    with staff_write(space_id):
        space, actor = scoped_space(actor, space_id, lock=True)
        row = target_row(space, membership_id, lock=True)
        require_authority(actor, space, target=row.user)
        if row.status != "active":
            raise ValidationError({"detail": "This staff row is already revoked."})
        protect_last_manager(space, row)
        _revoke_row(actor, space, row, reason)
    return target_row(space, row.pk)


def restore(actor, space_id, membership_id):
    with staff_write(space_id):
        space, actor = scoped_space(actor, space_id, lock=True)
        row = target_row(space, membership_id, lock=True)
        require_authority(actor, space, target=row.user)
        if row.status == "active":
            raise ValidationError({"detail": "This staff row is already active."})
        user = row.user
        if not user.is_active or user.access_status != User.AccessStatus.ACTIVE:
            raise ValidationError({"detail": "This account is disabled or restricted."})
        check_staff_quota(space)
        row.status, row.revoked_at, row.revoked_by, row.revocation_reason = "active", None, None, ""
        row.save(update_fields=["status", "revoked_at", "revoked_by", "revocation_reason"])
        record(actor, "staff_role.restored", makerspace=space, target=user, meta={"membership_id": row.pk})
    from apps.accounts.staff_role_notices import notify_granted
    notify_granted(row)
    return target_row(space, row.pk)


def _require_superadmin(actor, target):
    from apps.accounts.platform_authority import is_platform_superadmin
    from apps.accounts.staff_identity import is_person

    if not is_platform_superadmin(actor):
        raise PermissionDenied("Only the platform administrator disables accounts.")
    if not is_person(target):
        raise PermissionDenied("Only a personal account is disabled here.")


def disable_account(actor, user_id, *, reason=""):
    """Superadmin only: the account stops signing in everywhere; nothing is deleted.

    Every session and device grant is revoked and every active staff row is revoked
    (audited per space). Community memberships, history and money stay as they are.
    Superadmin authority outranks the last-manager rule: a space left without a manager
    is still managed by the superadmin (#110).
    """
    reason = _reason(reason, "Account disabled by the platform administrator")
    from apps.accounts.credential_revocation import revoke_all_credentials
    from apps.accounts.credential_locks import lock_credentials

    from apps.accounts.staff_account_policy import TENANT_GATED, StaffRoleRefused
    from apps.tenant_migration.gate_errors import SourceMigrationGateError
    from apps.tenant_migration.gate_runtime import assert_write_allowed

    target = User.objects.get(pk=user_id)
    _require_superadmin(actor, target)
    with transaction.atomic():
        spaces = MakerspaceMembership.staff_tracks.filter(user=target, status="active").values_list(
            "makerspace_id", flat=True)
        try:
            for space_id in sorted(set(spaces)):
                assert_write_allowed(space_id)
        except SourceMigrationGateError:
            raise StaffRoleRefused(TENANT_GATED, "A makerspace of this person is temporarily read-only.") from None
        revoke_all_credentials(target, reason="account.disabled", actor=actor)
        target = lock_credentials(target)
        if not target.is_active:
            raise ValidationError({"detail": "This account is already disabled."})
        target.is_active = False
        target.save(update_fields=["is_active"])
        rows = MakerspaceMembership.staff_tracks.select_related("makerspace").filter(user=target, status="active")
        for row in rows.order_by("makerspace_id"):
            _revoke_row(actor, row.makerspace, row, reason)
        record(actor, "account.disabled", target=target, meta={"reason": reason})
    return target


def enable_account(actor, user_id):
    """Superadmin only: undo ``disable_account``. Staff rows stay revoked (restore them
    per space); the person signs in again with their own credentials."""
    from apps.accounts.credential_locks import lock_credentials

    target = User.objects.get(pk=user_id)
    _require_superadmin(actor, target)
    with transaction.atomic():
        target = lock_credentials(target)
        if target.is_active:
            raise ValidationError({"detail": "This account is already enabled."})
        target.is_active = True
        target.save(update_fields=["is_active"])
        record(actor, "account.enabled", target=target)
    return target

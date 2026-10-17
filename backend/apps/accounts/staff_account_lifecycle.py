"""Transactional staff deactivation, reactivation and administrator password issue."""

import secrets

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.accounts.credential_revocation import revoke_all_credentials, revoke_sessions_only
from apps.accounts.credential_locks import lock_credentials
from apps.accounts.models import User
from apps.accounts.staff_account_policy import (
    protect_last_manager, require_authority, scoped_space, target_account,
)
from apps.audit.services import record
from apps.makerspaces import limits
from apps.makerspaces.models import MakerspaceMembership
from apps.tenant_migration.gate_runtime import tenant_write


def deactivate(actor, space_id, user_id, *, reason=""):
    if not isinstance(reason, str) or len(reason) > 200:
        raise ValidationError({"reason": "Use at most 200 characters."})
    with tenant_write(space_id):
        space, actor = scoped_space(actor, space_id, lock=True)
        target = target_account(space, user_id)
        require_authority(actor, space, target=target)
        membership = MakerspaceMembership.objects.get(user=target, makerspace=space)
        protect_last_manager(space, membership)
        # Revocation takes Invitations -> User -> Envelopes under our tenant lock.
        revoke_all_credentials(target, reason="staff_account.deactivated", actor=actor)
        target = lock_credentials(target)
        target.is_active = False
        target.must_change_password = True
        target.set_unusable_password()
        target.save(update_fields=["is_active", "must_change_password", "password"])
        membership.status, membership.revoked_at = "revoked", timezone.now()
        membership.revoked_by = actor
        membership.revocation_reason = reason.strip() or "Staff account deactivated"
        membership.can_refer = membership.can_verify = False
        membership.save(update_fields=["status", "revoked_at", "revoked_by", "revocation_reason",
                                       "can_refer", "can_verify"])
        record(actor, "staff.membership_revoked", makerspace=space, target=target,
               meta={"membership_role": membership.role})
        record(actor, "staff_account.deactivated", makerspace=space, target=target)
    return target


def reactivate(actor, space_id, user_id):
    with tenant_write(space_id):
        space, actor = scoped_space(actor, space_id, lock=True)
        target = target_account(space, user_id)
        require_authority(actor, space, target=target)
        target = lock_credentials(target)
        membership = MakerspaceMembership.objects.select_for_update().get(user=target, makerspace=space)
        if target.is_active and membership.status == "active":
            raise ValidationError({"detail": "This staff account is already active."})
        if not target.is_active and target.access_status == User.AccessStatus.ACTIVE:
            limits.check_quota(space, "staff", adding=1)
        target.is_active, target.must_change_password = True, True
        target.set_unusable_password()
        target.save(update_fields=["is_active", "must_change_password", "password"])
        membership.status = "active"
        membership.revoked_at = membership.revoked_by = None
        membership.revocation_reason = ""
        membership.save(update_fields=["status", "revoked_at", "revoked_by", "revocation_reason"])
        record(actor, "staff_account.reactivated", makerspace=space, target=target)
    return target


def set_password(actor, space_id, user_id, *, password=None, generate=False, reset_mfa=False):
    if (type(generate) is not bool or type(reset_mfa) is not bool
            or bool(password) == generate or (password is not None and
            (not isinstance(password, str) or len(password) > 1024))):
        raise ValidationError({"password": "Provide a password or generate=true, exclusively."})
    with tenant_write(space_id):
        space, actor = scoped_space(actor, space_id, lock=True)
        target = target_account(space, user_id)
        require_authority(actor, space, target=target)
        if not target.is_active:
            raise ValidationError({"detail": "Reactivate this account before setting a password."})
        candidate = secrets.token_urlsafe(24) if generate else password
        try:
            validate_password(candidate, user=target)
        except DjangoValidationError as exc:
            raise ValidationError({"password": exc.messages}) from exc
        revoke_sessions_only(target, reason="staff_account.password_reset", actor=actor)
        target = lock_credentials(target)
        target.set_password(candidate)
        target.must_change_password = True
        target.save(update_fields=["password", "must_change_password"])
        if reset_mfa:
            from apps.accounts.models_mfa import UserMFA
            # Deleting the factor also deletes its secret and recovery hashes; outstanding
            # MFA challenges are consumed so they cannot complete against a new factor.
            from apps.accounts.models import MFAChallenge
            MFAChallenge.objects.filter(user=target, consumed_at__isnull=True).update(consumed_at=timezone.now())
            UserMFA.objects.filter(user=target).delete()
        record(actor, "staff_account.password_reset", makerspace=space, target=target,
               meta={"reset_mfa": reset_mfa})
    return {"generated_password": candidate if generate else None}

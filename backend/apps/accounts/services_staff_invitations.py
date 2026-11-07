"""Staff-role invitations by email (one account per person, #63).

An invitation binds an email address, a role snapshot and a machine-scope snapshot. It
never creates an account: the invitee redeems it while signed in to their own account,
whose email must equal the invitation address and pass a fresh emailed code
(``staff_invitation_acceptance``). Accepting creates the person's staff-track row.
The link goes to the invitee only; it is never returned to the inviter.
"""

from django.utils.translation import gettext
import secrets
from datetime import timedelta

from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.accounts import audit_events, rbac
from apps.accounts.mfa_challenges import digest
from apps.accounts.models import StaffInvitation
from apps.accounts.staff_account_policy import require_authority, scoped_space, staff_write
from apps.audit.services import record
from apps.makerspaces.platform import feature_enabled, module_enabled
from apps.makerspaces.secrets import encrypt_value


def scoped(actor):
    return rbac.scope_by_action(actor, rbac.Action.MANAGE_MAKERSPACE, StaffInvitation.objects.all())


def onboarding_available(space):
    return module_enabled(space, "email") and feature_enabled(space, "staff.invitations")


def authority(actor, space, roles=None):
    if not onboarding_available(space):
        raise ValidationError({"detail": gettext("Email invitations are off for this makerspace. Grant the role to a "
                                         "community member instead.")})
    require_authority(actor, space, roles=roles)


def snapshot(roles, machine_type_ids):
    return {"role_snapshot": sorted(role.slug for role in roles),
            "machine_scope_snapshot": sorted(machine_type_ids),
            "granted_actions": sorted(set().union(*(set(role.granted_actions) for role in roles)))}


def _normalize(email):
    from django.core.exceptions import ValidationError as DjangoValidationError
    from django.core.validators import validate_email

    email = (email or "").strip().lower()
    try:
        validate_email(email)
    except DjangoValidationError as exc:
        raise ValidationError({"email": exc.messages}) from exc
    if len(email) > 254:
        raise ValidationError({"email": gettext("Use at most 254 characters.")})
    return email


def issue(actor, space_id, *, email, roles, machine_type_ids=(), expires_in_days=7):
    """Create an email invitation; returns ``(row, raw_token)``. Deliver after commit."""
    from apps.accounts.staff_account_services import resolve_machine_types, resolve_roles

    email = _normalize(email)
    if type(expires_in_days) is not int or not 1 <= expires_in_days <= 30:
        raise ValidationError({"expires_in_days": gettext("Use 1 to 30 days.")})
    with staff_write(space_id):
        space, actor = scoped_space(actor, space_id, lock=True)
        roles = resolve_roles(space, roles)
        authority(actor, space, roles)
        scopes = resolve_machine_types(space, roles, machine_type_ids)
        row, raw = _create(actor, space, email, roles, scopes, expires_in_days)
    return row, raw


def _create(actor, space, email, roles, scopes, expires_in_days):
    raw = secrets.token_urlsafe(32)
    row = StaffInvitation.objects.create(
        account=None, makerspace=space, role=roles[0], email_ciphertext=encrypt_value(email),
        token_digest=digest(raw), expires_at=timezone.now() + timedelta(days=expires_in_days),
        created_by=actor, credential_generation=0, **snapshot(roles, scopes),
    )
    record(actor, "staff_invitation.sent", makerspace=space, target=row,
           meta={"roles": row.role_snapshot, "machine_type_ids": row.machine_scope_snapshot,
                 "email_hash": audit_events.fingerprint(email), "expires_at": row.expires_at.isoformat()})
    return row, raw


def _open_row(actor, space, invitation_id):
    row = get_object_or_404(scoped(actor).select_for_update(), pk=invitation_id, makerspace=space)
    if row.accepted_at or row.revoked_at:
        raise ValidationError({"detail": gettext("This invitation is no longer open.")})
    return row


def resend(actor, space_id, invitation_id):
    """A fresh link for the same address and roles; the old link stops working."""
    with staff_write(space_id):
        space, actor = scoped_space(actor, space_id, lock=True)
        row = _open_row(actor, space, invitation_id)
        roles = list(space.roles.filter(slug__in=row.role_snapshot))
        authority(actor, space, roles)
        row.revoked_at = timezone.now()
        row.save(update_fields=["revoked_at"])
        new, raw = _create(actor, space, row.email, roles, row.machine_scope_snapshot, 7)
    return new, raw


def revoke(actor, space_id, invitation_id):
    with staff_write(space_id):
        space, actor = scoped_space(actor, space_id, lock=True)
        row = _open_row(actor, space, invitation_id)
        require_authority(actor, space, roles=list(space.roles.filter(slug__in=row.role_snapshot)))
        row.revoked_at = timezone.now()
        row.save(update_fields=["revoked_at"])
        record(actor, "staff_invitation.revoked", makerspace=space, target=row)
    return row

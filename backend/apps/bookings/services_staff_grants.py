"""Booking target adapter for the shared audited, locked grant lifecycle."""

import logging
from dataclasses import replace

from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.makerspaces import resource_grants_services as lifecycle
from apps.makerspaces.guards import require_module_locked
from apps.makerspaces.platform import feature_enabled
from apps.makerspaces.resource_grant_locks import lock_tenant_authority

from . import booking_authority
from .booking_permissions import PERMISSIONS
from .models import BookableSpace
from .models_staff_grants import BookingSpaceStaffGrant, BookingSpaceStaffGrantInvite

logger = logging.getLogger(__name__)


def require_feature(space):
    if not feature_enabled(space.makerspace, "bookings.staff_grants"):
        raise ValidationError({"feature": "Booking staff grants are disabled."})


def _locked_target(target):
    from apps.tenant_migration.gate_runtime import assert_write_allowed
    assert_write_allowed(target.makerspace_id)
    locked = BookableSpace.objects.select_for_update().get(pk=target.pk)
    locked.makerspace = require_module_locked(locked.makerspace_id, "bookings")
    if not booking_authority._servable(locked):
        raise PermissionDenied()
    require_feature(locked)
    return locked


def _locked_visible_target(target):
    locked = _locked_target(target)
    if not locked.makerspace.superadmin_access_enabled:
        raise PermissionDenied("Resource invitations are unavailable while this makerspace is hidden.")
    return locked


ADAPTER = lifecycle.GrantAdapter(
    grant_model=BookingSpaceStaffGrant, invite_model=BookingSpaceStaffGrantInvite,
    permissions=PERMISSIONS, namespace="bookings", audit_prefix="booking.staff_grant",
    target=lambda row: row.space, lock_target=_locked_target,
    scope=lambda space: {"makerspace_id": space.makerspace_id, "space": space},
    can_manage=booking_authority.can_manage_grants, can=booking_authority.can,
    active=booking_authority.active, lock_authority=lock_tenant_authority,
)


def create_invite(target, *, actor, permissions, email="", send_email=False):
    return lifecycle.create_invite(replace(ADAPTER, lock_target=_locked_visible_target), target, actor=actor, permissions=permissions,
                                   email=email, send=_send_invite if send_email else None)


def update_permissions(grant, *, actor, permissions):
    return lifecycle.update_permissions(ADAPTER, grant, actor=actor, permissions=permissions)


def revoke_grant(grant, *, actor):
    return lifecycle.revoke_grant(ADAPTER, grant, actor=actor)


def revoke_invite(invite, *, actor):
    return lifecycle.revoke_invite(ADAPTER, invite, actor=actor)


def redeem_invite(token, *, actor, makerspace_id=None):
    return lifecycle.redeem_invite(replace(ADAPTER, lock_target=_locked_visible_target), token, actor=actor, makerspace_id=makerspace_id)


def _send_invite(row, email, token):
    from urllib.parse import quote
    from apps.integrations.dispatch_outbox import dispatch_email
    from apps.makerspaces.platform import member_area_url
    try:
        base = member_area_url(row.makerspace).split("/m/", 1)[0].removesuffix("/member")
        link = f"{base.rstrip('/')}/staff/booking-invite#token={quote(token)}"
        dispatch_email(to_email=email, subject="Booking resource staff invitation",
                       text_body=f"Accept your resource staff invitation: {link}",
                       makerspace=row.makerspace, persist_body=False, sync=True,
                       stream="bookings", event="booking_staff_invitation", audience="staff")
    except Exception:
        logger.error("booking_staff_invitation_email_failed", extra={"invite_id": row.pk})

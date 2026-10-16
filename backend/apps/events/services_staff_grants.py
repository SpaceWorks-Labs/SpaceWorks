"""Events owns target policy; always-present infrastructure owns the lifecycle."""

import logging

from rest_framework.exceptions import PermissionDenied

from apps.makerspaces import resource_grants_services as lifecycle
from apps.makerspaces.guards import require_module_locked
from apps.makerspaces.servability import is_servable

from . import event_authority
from .event_permissions import PERMISSIONS
from .models import EventStaffGrant, EventStaffGrantInvite
from .staff_grant_locks import lock_authority

logger = logging.getLogger(__name__)


def _target(row):
    return row.event if row.event_id else row.series


def _locked_target(target):
    # Preserve the events lock order: event/series -> makerspace -> credential.
    locked = type(target).objects.select_for_update().get(pk=target.pk)
    from apps.tenant_migration.gate_runtime import assert_write_allowed
    assert_write_allowed(locked.makerspace_id)
    locked.makerspace = require_module_locked(locked.makerspace_id, "events")
    if not is_servable(locked.makerspace):
        raise PermissionDenied()
    return locked


def _scope(target):
    return {"makerspace_id": target.makerspace_id,
            "series" if event_authority._is_series(target) else "event": target}


ADAPTER = lifecycle.GrantAdapter(
    grant_model=EventStaffGrant, invite_model=EventStaffGrantInvite,
    permissions=PERMISSIONS, namespace="events", audit_prefix="event.staff_grant",
    target=_target, lock_target=_locked_target, scope=_scope,
    can_manage=event_authority.can_manage_grants, can=event_authority.can,
    active=event_authority._active,
    lock_authority=lock_authority,
    label_field="role_label",
)


def create_invite(target, *, actor, permissions, email="", send_email=False, role_label=""):
    return lifecycle.create_invite(
        ADAPTER, target, actor=actor, permissions=permissions, email=email,
        send=_send_invite if send_email else None, label=role_label,
    )


def update_permissions(grant, *, actor, permissions, role_label=None):
    return lifecycle.update_permissions(
        ADAPTER, grant, actor=actor, permissions=permissions, label=role_label,
    )


def revoke_grant(grant, *, actor):
    return lifecycle.revoke_grant(ADAPTER, grant, actor=actor)


def revoke_invite(invite, *, actor):
    return lifecycle.revoke_invite(ADAPTER, invite, actor=actor)


def redeem_invite(token, *, actor, makerspace_id=None):
    return lifecycle.redeem_invite(ADAPTER, token, actor=actor, makerspace_id=makerspace_id)


def _send_invite(row, email, token):
    from urllib.parse import quote
    from apps.integrations.dispatch_outbox import dispatch_email
    from apps.makerspaces.platform import member_area_url

    try:
        base = member_area_url(row.makerspace).split("/m/", 1)[0].removesuffix("/member")
        # Fragment credentials do not enter HTTP referrers or server access logs.
        link = f"{base.rstrip('/')}/staff/event-invite#token={quote(token)}"
        dispatch_email(to_email=email, subject="Event staff invitation",
                       text_body=f"Accept your event staff invitation: {link}",
                       makerspace=row.makerspace, persist_body=False, sync=True,
                       stream="events", event="event_staff_invitation", audience="staff")
    except Exception:
        logger.error("event_staff_invitation_email_failed", extra={"invite_id": row.pk})

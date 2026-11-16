"""Events owns target policy; always-present infrastructure owns the lifecycle."""

from django.utils.translation import gettext
import logging

from rest_framework.exceptions import PermissionDenied

from apps.makerspaces import resource_grants_services as lifecycle
from apps.makerspaces.guards import require_module_locked
from apps.makerspaces.servability import is_servable

from . import event_authority
from .event_permissions import PERMISSIONS
from .models import EventStaffGrant, EventStaffGrantInvite
from .staff_grant_locks import lock_authority
from .contributions.authority import subset_validator
from .contributions.grant_sources import manual_changed

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


def _can_within_limit(actor, target, permission):
    """`event_authority.can`, asked about the invite's tracks when a limit is in play (221i).

    A track-limited co-organizer holds no unscoped authority, so the lifecycle's revalidation
    of a delegated permission must ask about the very tracks the invitation covers.
    """
    from . import staff_grant_limits as limits
    limit = limits.current_limit()
    if limit and limit[0]:
        return all(event_authority.can(actor, target, permission, track_id=t) for t in limit[0])
    return event_authority.can(actor, target, permission)


ADAPTER = lifecycle.GrantAdapter(
    grant_model=EventStaffGrant, invite_model=EventStaffGrantInvite,
    permissions=PERMISSIONS, namespace="events", audit_prefix="event.staff_grant",
    target=_target, lock_target=_locked_target, scope=_scope,
    can_manage=event_authority.can_manage_grants, can=_can_within_limit,
    active=event_authority._active,
    lock_authority=lock_authority,
    label_field="role_label",
    subset_validator=subset_validator,
    grant_written=manual_changed,
)


def create_invite(target, *, actor, permissions, email="", send_email=False, role_label="",
                  track_ids=(), valid_from=None, valid_until=None):
    from .services_write_boundary import write_boundary
    from . import staff_grant_limits as limits
    with write_boundary(target, actor=actor):
        # Decision 221(i): a limited co-organizer's invite inherits (or narrows) their own limit.
        tracks, start, end = limits.resolve(actor=actor, event=target, permissions=permissions,
                                            track_ids=track_ids, valid_from=valid_from, valid_until=valid_until)
        with limits.limit_in_play(tracks, start, end):
            row, token = lifecycle.create_invite(
                ADAPTER, target, actor=actor, permissions=permissions, email=email,
                send=_send_invite if send_email else None, label=role_label)
        if tracks or start or end:
            row.track_ids, row.valid_from, row.valid_until = tracks, start, end
            row.save(update_fields=["track_ids", "valid_from", "valid_until"])
        return row, token


def update_permissions(grant, *, actor, permissions, role_label=None):
    from .services_write_boundary import write_boundary
    with write_boundary(_target(grant), actor=actor, account_ids=(grant.user_id,)):
        return lifecycle.update_permissions(
            ADAPTER, grant, actor=actor, permissions=permissions, label=role_label)


def revoke_grant(grant, *, actor):
    from .services_write_boundary import write_boundary
    from apps.audit.services import record
    with write_boundary(_target(grant), actor=actor, account_ids=(grant.user_id,)):
        target = ADAPTER.lock_target(_target(grant))
        actor = lock_authority(actor, target)
        row = EventStaffGrant.objects.select_for_update().get(pk=grant.pk)
        lifecycle._require_subset(ADAPTER, actor, target, (), operation="revoke_grant", row=row, authority_locked=True)
        manual_changed(grant=row, permissions=(), actor=actor, operation="revoke_grant")
        record(actor, "event.staff_grant_manual_revoked", makerspace=row.makerspace, target=row)
        return row


def revoke_invite(invite, *, actor):
    from .services_write_boundary import write_boundary
    with write_boundary(_target(invite), actor=actor):
        return lifecycle.revoke_invite(ADAPTER, invite, actor=actor)


def redeem_invite(token, *, actor, makerspace_id=None):
    from .services_write_boundary import write_boundary
    from rest_framework.exceptions import NotFound
    digest = lifecycle.credential_digest(token, namespace="events", purpose="invite")
    invite = EventStaffGrantInvite.objects.filter(token_digest=digest).first()
    if invite is None or (makerspace_id is not None and invite.makerspace_id != makerspace_id):
        raise NotFound()
    from .programme.commands import ProgrammeConflict
    from .services_write_boundary import SCOPE_RETRIES, _held
    # A concurrent redeemer's new grant grows the event's account scope between
    # discovery and the lock; nothing is written yet, so re-discover and retry (the
    # loser then meets the consumed invite as NotFound) instead of failing with 409.
    attempts = 1 if _held.get() is not None else SCOPE_RETRIES
    for attempt in range(attempts):
        try:
            with write_boundary(_target(invite), actor=actor,
                                account_ids=tuple(x for x in (invite.created_by_id,) if x)):
                from .staff_grant_limits import limit_in_play
                with limit_in_play(invite.track_ids, invite.valid_from, invite.valid_until):
                    return lifecycle.redeem_invite(ADAPTER, token, actor=actor, makerspace_id=makerspace_id)
        except ProgrammeConflict as exc:
            if attempt + 1 == attempts or str(exc.detail.get("code")) != "scope_changed":
                raise


def _send_invite(row, email, token):
    from urllib.parse import quote
    from apps.integrations.dispatch_outbox import dispatch_email
    from apps.makerspaces.platform import member_area_url

    try:
        base = member_area_url(row.makerspace).split("/m/", 1)[0].removesuffix("/member")
        # Fragment credentials do not enter HTTP referrers or server access logs.
        link = f"{base.rstrip('/')}/staff/event-invite#token={quote(token)}"
        dispatch_email(to_email=email, subject=gettext("Event staff invitation"),
                       text_body=gettext('Accept your event staff invitation: {link}').format(link=link),
                       makerspace=row.makerspace, persist_body=False, sync=True,
                       stream="events", event="event_staff_invitation", audience="staff")
        from apps.integrations.invite_chat import dispatch_invite_chat  # X37: chat beside email
        dispatch_invite_chat(row.makerspace, feature="events", invite=row, email=email,
                             label="You are invited to help run an event", link=link)
    except Exception:
        logger.error("event_staff_invitation_email_failed", extra={"invite_id": row.pk})

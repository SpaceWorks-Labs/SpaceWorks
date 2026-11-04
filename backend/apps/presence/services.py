"""Transactional presence writers. Lock tenant, then account, then session."""

from apps.accounts.account_kind_guards import require_member_account
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.accounts.claim_sessions import claim_context, token_payload_for_context, validated_claim_session
from apps.audit import services as audit
from apps.tenant_migration.gate_runtime import tenant_write
from .geofence import require_inside
from .models import PresencePreference, PresenceSession, PresenceSettings
from .policy import PresenceError, owned_project, presets, require_account, require_staff, validate_duration
from .renewal import renewal_expiry
from .services_claim import (
    _validate_claim_scope, end_sessions_for_claim, end_sessions_for_membership, expire_claim_presence,
)


def _lock_account(user, space):
    from apps.makerspaces.models import Makerspace
    context = claim_context(user)
    space = Makerspace.objects.select_for_update(no_key=True).get(pk=space.pk)
    PresenceSettings.objects.get_or_create(makerspace=space)
    user = get_user_model().objects.select_for_update(no_key=True).get(pk=user.pk)
    if context is not None:
        user._claim_audit_context = context
    return user, space


def _claim(user, space, *, for_update=True):
    context = claim_context(user)
    if context is None:
        return None
    claim = validated_claim_session(token_payload_for_context(context, user.pk), for_update=for_update)
    _validate_claim_scope(claim, user, space)
    return claim


def _rows(user, space):
    return PresenceSession.objects.select_for_update().filter(
        account=user, makerspace=space, ended_at=None).order_by("-started_at", "-pk")


def _end(session, actor, reason, now):
    session.ended_at, session.ended_by, session.end_reason = now, actor, reason
    session.save(update_fields=["ended_at", "ended_by", "end_reason"])
    audit.record(actor, "presence.ended", makerspace=session.makerspace, target=session,
                 meta={"reason": reason})


def _create(user, space, membership, duration, *, actor, status, project=None,
            hide_on_display=None, claim=None, registration=None):
    require_member_account(user)
    now = timezone.now()
    expiry = now + timedelta(minutes=duration)
    if registration:
        expiry = min(expiry, registration.event.ends_at)
    if claim:
        expiry = min(expiry, claim.absolute_expires_at)
    if expiry <= now:
        raise PresenceError("presence_expired", "The check-in authorization has expired.")
    active = list(_rows(user, space))
    for row in active:
        if (row.expires_at > now and row.expires_at - row.started_at == timedelta(minutes=duration)
                and row.status == status and row.project_id == getattr(project, "pk", None)
                and row.event_registration_id == getattr(registration, "pk", None)
                and row.created_via_claim_session_id == getattr(claim, "pk", None)
                and (hide_on_display is None or row.hide_on_display == hide_on_display)):
            return row
    for row in active:
        reason = "expired" if row.expires_at <= now else "superseded"
        _end(row, actor, reason, min(now, row.expires_at))
    if claim:
        # Temporary authority may read the existing default, never persist consent.
        preference = PresencePreference.objects.filter(makerspace=space, account=user).first()
        hidden = hide_on_display if hide_on_display is not None else bool(preference and preference.hide_on_display)
    else:
        preference, _ = PresencePreference.objects.get_or_create(makerspace=space, account=user)
        hidden = preference.hide_on_display if hide_on_display is None else hide_on_display
    if not claim and hide_on_display is not None and preference.hide_on_display != hide_on_display:
        preference.hide_on_display = hide_on_display
        preference.save(update_fields=["hide_on_display"])
        audit.record(actor, "presence.preference_updated", makerspace=space, target=preference)
    session = PresenceSession.objects.create(
        account=user, member=user, makerspace=space, membership=membership,
        started_at=now, expires_at=expiry, status=status, project=project,
        hide_on_display=hidden, created_via_claim_session=claim,
        event_registration=registration,
    )
    audit.record(actor, "presence.started", makerspace=space, target=session,
                 meta={"status": status, "staff_recorded": actor.pk != user.pk})
    return session


def start_session(user, makerspace, duration_minutes, *, latitude=None, longitude=None,
                  accuracy=None, status=None, project_id=None, hide_on_display=None):
    return _start(user, makerspace, duration_minutes, actor=user, staff=False,
                  latitude=latitude, longitude=longitude, accuracy=accuracy, status=status,
                  project_id=project_id, hide_on_display=hide_on_display)


def staff_check_in(actor, user, space, duration_minutes, **options):
    return _start(user, space, duration_minutes, actor=actor, staff=True, **options)


def _start(user, space, duration, *, actor, staff, latitude=None, longitude=None,
           accuracy=None, status=None, project_id=None, hide_on_display=None):
    require_member_account(user)
    with tenant_write(space.pk):
        claim = _claim(user, space)
        context = claim_context(user)
        user, space = _lock_account(user, space)
        if staff:
            require_staff(actor, space)
        membership = require_account(user, space)
        if staff and membership is None:
            # Staff record people on this roster (members, or this space's walk-ins);
            # account-only guests check themselves in inside the geofence.
            raise PresenceError("account_not_in_space", "Use a member or walk-in from this makerspace.", status_code=403)
        if context and (membership is None or context.membership_id != membership.pk):
            raise PresenceError("claim_scope", "Claim session belongs to another makerspace.", status_code=403)
        validate_duration(space, duration)
        if not staff:
            require_inside(space, latitude=latitude, longitude=longitude, accuracy=accuracy)
        if user.is_walk_in and not staff and claim is None:
            raise PresenceError("walk_in_staff_required", "Ask staff to check in this walk-in.", status_code=403)
        guest = membership is None or (staff and user.is_walk_in)
        status = status or ("guest" if guest else "visiting")
        if status not in {"working", "visiting", "guest"} or (guest != (status == "guest")):
            raise PresenceError("invalid_presence_status", "Choose an eligible status; event attendance requires a live ticket check-in.")
        project = owned_project(user, space, project_id, status)
        return _create(user, space, membership, duration, actor=actor, status=status,
                       project=project, hide_on_display=hide_on_display, claim=claim)


def current_session(user, makerspace):
    require_account(user, makerspace)
    rows = PresenceSession.objects.filter(account=user, makerspace=makerspace, ended_at=None,
                                           expires_at__gt=timezone.now())
    context = claim_context(user)
    if context:
        rows = rows.filter(created_via_claim_session__session_id=context.session_id,
                           expires_at__lte=context.absolute_expires_at)
    return rows.order_by("-started_at", "-pk").first()


def renewable_session(user, space):
    """Return only the latest session, expired but still eligible for renewal."""
    require_account(user, space)
    claim = _claim(user, space, for_update=False)
    row = PresenceSession.objects.filter(account=user, makerspace=space).order_by("-started_at", "-pk").first()
    now = timezone.now()
    if row is None or row.expires_at > now:
        return None
    try:
        renewal_expiry(row, space, now=now, duration_minutes=presets(space)[0], claim=claim)
    except PresenceError:
        return None
    return row


def renew_session(user, space, duration_minutes):
    with tenant_write(space.pk):
        claim = _claim(user, space)
        user, space = _lock_account(user, space)
        require_account(user, space)
        validate_duration(space, duration_minutes)
        row = PresenceSession.objects.select_for_update().filter(account=user, makerspace=space).order_by("-started_at", "-pk").first()
        expiry = renewal_expiry(row, space, now=timezone.now(), duration_minutes=duration_minutes, claim=claim)
        row.expires_at, row.expiry_reminded_at = expiry, None
        row.ended_at, row.ended_by, row.end_reason = None, None, ""
        row.revision += 1
        row.save(update_fields=["expires_at", "expiry_reminded_at", "revision", "ended_at", "ended_by", "end_reason"])
        audit.record(user, "presence.renewed", makerspace=space, target=row)
        return row


def end_session(user, makerspace, *, actor=None):
    actor = actor or user
    with tenant_write(makerspace.pk):
        claim = _claim(user, makerspace)
        user, makerspace = _lock_account(user, makerspace)
        if actor.pk != user.pk:
            require_staff(actor, makerspace)
        else:
            require_account(user, makerspace)
        rows = _rows(user, makerspace)
        if claim:
            rows = rows.filter(created_via_claim_session=claim)
        for row in rows:
            reason = "user_ended" if actor.pk == user.pk else "staff_ended"
            _end(row, actor, reason, timezone.now())

"""Open and close a superadmin's audited PII window (owner decision #111 Q12).

A window is 30 minutes, needs a reason (10-300 characters) and recent re-authentication
(the caller checks that: ``require_recent_reauth`` on the API, the /control/ step-up on
admin pages; a password is enough, MFA is not demanded). Opening, closing and expiry each
write a makerspace-scoped audit row the space's managers can read in their audit log. A
per-person window is audited in EVERY space that person belongs to.

Expiry is closed lazily: any read of a superadmin's windows (masking, the status
endpoint) first closes that superadmin's lapsed windows and records the expiry with the
real expiry time as ``closed_at``. The ``expire_pii_access_windows_task`` beat sweep
closes the rest the same way, so a window nobody reads again still gets its expiry row
in the space's audit log. No mail is sent.
"""

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import APIException, PermissionDenied

from apps.accounts.models_pii_access import WINDOW, PlatformPiiAccessGrant
from apps.accounts.platform_authority import is_platform_superadmin
from apps.audit import services as audit

SPACE, PERSON = "space", "person"


class PiiAccessAlreadyOpen(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_code = "pii_access_already_open"
    default_detail = "A PII access window is already open here. Close it before opening another."


def clean_reason(reason):
    reason = " ".join(str(reason or "").split())
    if not 10 <= len(reason) <= 300:
        raise ValidationError("Give a reason of 10 to 300 characters.", code="invalid_pii_reason")
    return reason


def _open_q(now):
    return {"closed_at__isnull": True, "expires_at__gt": now}


def active_grants(viewer, now=None):
    now = now or timezone.now()
    if not is_platform_superadmin(viewer):
        return PlatformPiiAccessGrant.objects.none()
    sweep_expired(actor=viewer, now=now)
    return PlatformPiiAccessGrant.objects.filter(actor=viewer, opened_at__lte=now, **_open_q(now))


def _audit_spaces(grant):
    """The spaces an audit row is written to: the window's space, or the person's spaces."""
    from apps.makerspaces.models import Makerspace
    if grant.makerspace_id is not None:
        return [grant.makerspace]
    from apps.accounts.pii_presentation import person_space_ids
    ids = person_space_ids(grant.subject)
    return list(Makerspace.objects.filter(pk__in=ids).order_by("pk")) or [None]


def _scope(grant):
    scope = SPACE if grant.makerspace_id is not None else PERSON
    return scope, grant.makerspace if scope == SPACE else grant.subject


def _record_opened(actor, grant):
    scope, target = _scope(grant)
    for space in _audit_spaces(grant):
        audit.record(actor, "platform.pii_access_opened", makerspace=space, target=target, meta={
            "scope": scope, "reason": grant.reason, "expires_at": grant.expires_at.isoformat()})


def _record_closed(actor, grant):
    scope, target = _scope(grant)
    for space in _audit_spaces(grant):
        audit.record(actor, "platform.pii_access_closed", makerspace=space, target=target, meta={
            "scope": scope, "close_reason": grant.close_reason, "closed_at": grant.closed_at.isoformat()})


def _require_superadmin(actor):
    if not is_platform_superadmin(actor):
        raise PermissionDenied("Only a platform superadmin opens a PII access window.")


@transaction.atomic
def open_grant(actor, space, reason):
    """Open a 30-minute window on one makerspace's PII."""
    _require_superadmin(actor)
    reason = clean_reason(reason)
    from apps.makerspaces.models import Makerspace
    from apps.makerspaces.servability import is_servable
    space = Makerspace.objects.select_for_update().get(pk=space.pk)
    if not is_servable(space):
        raise PermissionDenied("This makerspace is not available.")
    return _open(actor, reason, makerspace=space)


@transaction.atomic
def open_person_grant(actor, person, reason):
    """Open a 30-minute window on one person's PII in every space they belong to."""
    _require_superadmin(actor)
    reason = clean_reason(reason)
    from apps.accounts.models import User
    person = User.objects.select_for_update().get(pk=person.pk)
    if person.account_kind == "platform":
        raise ValidationError("Platform accounts are not masked.", code="invalid_pii_subject")
    return _open(actor, reason, subject=person)


def _open(actor, reason, **scope):
    now = timezone.now()
    sweep_expired(actor=actor, now=now)
    if PlatformPiiAccessGrant.objects.filter(actor=actor, **scope, **_open_q(now)).exists():
        raise PiiAccessAlreadyOpen()
    grant = PlatformPiiAccessGrant.objects.create(
        actor=actor, reason=reason, opened_at=now, expires_at=now + WINDOW, **scope)
    _record_opened(actor, grant)
    from apps.accounts.pii_presentation import forget
    forget(actor)
    return grant


def _close(grant, actor, close_reason, closed_at):
    grant.closed_at, grant.close_reason = closed_at, close_reason
    grant.save(update_fields=["closed_at", "close_reason"])
    _record_closed(actor, grant)


@transaction.atomic
def close_grant(actor, grant):
    """Close a window early. Only the superadmin who opened it closes it."""
    _require_superadmin(actor)
    grant = PlatformPiiAccessGrant.objects.select_for_update().get(pk=grant.pk)
    if grant.actor_id != actor.pk:
        raise PermissionDenied("Only the superadmin who opened this window can close it.")
    now = timezone.now()
    if grant.closed_at is not None:
        return grant
    if grant.expires_at <= now:
        _close(grant, grant.actor, PlatformPiiAccessGrant.CloseReason.EXPIRED, grant.expires_at)
    else:
        _close(grant, actor, PlatformPiiAccessGrant.CloseReason.CLOSED, now)
    from apps.accounts.pii_presentation import forget
    forget(actor)
    return grant


def sweep_expired(*, actor=None, makerspace_id=None, now=None, limit=None):
    """Close and audit lapsed windows (oldest expiry first); returns how many were closed."""
    now = now or timezone.now()
    rows = PlatformPiiAccessGrant.objects.filter(closed_at__isnull=True, expires_at__lte=now)
    if actor is not None:
        rows = rows.filter(actor=actor)
    if makerspace_id is not None:
        rows = rows.filter(makerspace_id=makerspace_id)
    pks = rows.order_by("expires_at", "pk").values_list("pk", flat=True)
    closed = 0
    for pk in (pks[:limit] if limit is not None else pks):
        with transaction.atomic():
            grant = (PlatformPiiAccessGrant.objects.select_for_update().select_related("actor")
                     .filter(pk=pk, closed_at__isnull=True).first())
            if grant is None:
                continue
            _close(grant, grant.actor, PlatformPiiAccessGrant.CloseReason.EXPIRED, grant.expires_at)
            closed += 1
    return closed

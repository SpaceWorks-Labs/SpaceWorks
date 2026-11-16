from django.utils.translation import gettext
from collections import Counter
from uuid import UUID

from django.core import signing
from django.db import IntegrityError
from django.utils import timezone
from rest_framework.exceptions import AuthenticationFailed, PermissionDenied

from apps.events.checkin_policy import reported_time_is_valid, sync_is_open
from apps.events.checkin_tokens import read_lease
from apps.events.exceptions import (
    CheckInLeaseExpired,
    DuplicateCheckInOperation,
    EventInvalidTransition,
)
from apps.events.models import Event, EventCheckInEvent, EventRegistration
from apps.events.services_checkin import mark_attended_with_event
from apps.makerspaces.community_policy import CommunityError
from apps.payments.event_payouts.errors import PayoutError


def validated_lease(
    token,
    event,
    *,
    kind,
    actor=None,
    session_id=None,
    station_version=None,
):
    try:
        lease = read_lease(token)
    except (signing.BadSignature, TypeError, ValueError, KeyError):
        raise AuthenticationFailed(gettext("Invalid check-in lease.")) from None
    expected = (
        lease.get("kind") == kind
        and lease.get("event_id") == event.pk
        and lease.get("makerspace_id") == event.makerspace_id
        and lease.get("actor_id") == (actor.pk if actor is not None else None)
        and lease.get("station_version") == station_version
        and (session_id is None or lease.get("lease_id") == str(session_id))
    )
    if not expected:
        raise PermissionDenied(gettext("Check-in lease authority changed."))
    if not sync_is_open(lease):
        raise CheckInLeaseExpired()
    return lease


def synchronize(
    event,
    operations,
    *,
    lease,
    actor,
    source,
    session_id,
    station_version=None,
    badge_receipts=None,
):
    results = [
        _process(
            event,
            item,
            lease=lease,
            actor=actor,
            source=source,
            session_id=session_id,
            station_version=station_version,
        )
        for item in operations
    ]
    from apps.events import services

    counts = Counter(result["outcome"] for result in results)
    services._audit(
        event,
        actor,
        "event.checkin_sync_processed",
        event,
        {
            "lease_id": lease["lease_id"],
            "station_version": station_version,
            "operation_count": len(results),
            "outcomes": dict(sorted(counts.items())),
        },
    )
    payload = {"recorded_at": timezone.now(), "results": results}
    if badge_receipts:
        from .badge_prints import desk_print_on, record_receipts
        if desk_print_on(event.makerspace):
            # Offline prints are never blocked by the monthly limit; they count when they sync (E-B2).
            recorded, duplicates = record_receipts(event, badge_receipts, actor=actor, method="offline")
            payload["badge_receipts"] = {"recorded": recorded, "duplicates": duplicates}
    return payload


def _registration_for(event, raw):
    """The registration a scanned code belongs to: a legacy UUID, or (badge desk print on) a live SWEC2 code."""
    raw = str(raw or "")
    if raw.startswith("SWEC2."):
        from apps.events.badge_prints import desk_print_on
        if not desk_print_on(event.makerspace):
            return None
        from apps.events.credentials.crypto import token_digest
        from apps.events.credentials.models import EventRegistrationCredential
        digest = token_digest(event.pk, raw)
        credential = EventRegistrationCredential.objects.filter(
            token_digest=digest, registration__event=event, registration__credential_mode="v2",
            revoked_at__isnull=True, expires_at__gt=timezone.now(),
        ).select_related("registration").first() if digest else None
        return credential.registration if credential is not None else None
    try:
        token = UUID(raw)
    except (TypeError, ValueError, AttributeError):
        return None
    return EventRegistration.objects.filter(event=event, checkin_token=token, credential_mode="legacy").first()


def _process(event, item, *, lease, actor, source, session_id, station_version):
    operation_id = item["operation_id"]
    base = {"operation_id": operation_id}
    if EventCheckInEvent.objects.filter(
        makerspace_id=event.makerspace_id,
        operation_id=operation_id,
    ).exists():
        return {**base, "outcome": "duplicate_operation"}
    if event.status not in (Event.Status.PUBLISHED, Event.Status.COMPLETED):
        return {**base, "outcome": "event_unavailable"}
    if not reported_time_is_valid(item["reported_occurred_at"], lease):
        return {**base, "outcome": "outside_window"}
    registration = _registration_for(event, item["checkin_token"])
    if registration is None:
        return {**base, "outcome": "invalid_token"}
    if registration.status == EventRegistration.Status.ATTENDED:
        return {**base, "outcome": "already_attended"}
    if registration.status != EventRegistration.Status.REGISTERED:
        return {**base, "outcome": "registration_changed"}
    try:
        updated, check_in = mark_attended_with_event(
            registration,
            actor=actor,
            source=source,
            operation_id=operation_id,
            attended_at=item["reported_occurred_at"],
            session_id=session_id,
            station_version=station_version,
        )
    except DuplicateCheckInOperation:
        return {**base, "outcome": "duplicate_operation"}
    except PayoutError as exc:
        if exc.detail.get("code") != "stage_incomplete":
            raise
        return {**base, "outcome": "stage_incomplete"}
    except CommunityError as exc:
        # EV-27: a minor's guardian consent is missing, expired or withdrawn; report the typed code.
        return {**base, "outcome": exc.error_code}
    except IntegrityError:
        # With the event and registration locked, the remaining expected race is the
        # globally unique operation UUID. Do not query another tenant to prove that
        # collision: the uniform idempotent outcome reveals no cross-tenant row.
        return {**base, "outcome": "duplicate_operation"}
    except EventInvalidTransition:
        fresh_event = Event.objects.only("status").get(pk=event.pk)
        if fresh_event.status not in (Event.Status.PUBLISHED, Event.Status.COMPLETED):
            return {**base, "outcome": "event_unavailable"}
        fresh = EventRegistration.objects.filter(pk=registration.pk).first()
        if fresh and fresh.status == EventRegistration.Status.ATTENDED:
            return {**base, "outcome": "already_attended"}
        return {**base, "outcome": "registration_changed"}
    return {
        **base,
        "outcome": "applied",
        "registration_id": updated.pk,
        "attended_at": check_in.attended_at,
    }

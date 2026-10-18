from uuid import uuid4

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied

from apps.events.exceptions import DuplicateCheckInOperation, EventInvalidTransition
from apps.events.models import (
    Event,
    EventCheckInEvent,
    EventRegistration,
)
from apps.events.services_station import credential_for_event
from apps.makerspaces.guards import require_feature_locked
from .services_write_boundary import event_write


FEATURE_SOURCES = {
    EventCheckInEvent.Source.OFFLINE_SYNC,
    EventCheckInEvent.Source.VENUE_STATION,
}


def _boundary():
    from apps.events import services

    return services


def _lock_registration(event, registration_id):
    registration = EventRegistration.objects.select_for_update().get(pk=registration_id)
    if registration.event_id != event.pk:
        raise EventInvalidTransition("Registration does not belong to this event.")
    registration.event = event
    return registration


@event_write
def mark_attended_with_event(
    registration,
    *,
    actor,
    source=EventCheckInEvent.Source.ONLINE,
    operation_id=None,
    attended_at=None,
    session_id=None,
    station_version=None,
):
    services = _boundary()
    event = services._locked_event(registration.event_id)
    locked = _lock_registration(event, registration.pk)
    return mark_attended_locked(event, locked, actor=actor, source=source,
        operation_id=operation_id, attended_at=attended_at, session_id=session_id,
        station_version=station_version)


def mark_attended_locked(event, locked, *, actor, source=EventCheckInEvent.Source.ONLINE,
                         operation_id=None, attended_at=None, session_id=None, station_version=None):
    """Sole attendance writer, reusing scanner-owned locked/prepared registration."""
    from .programme_locks import current_locks, assert_lock_context
    context = current_locks(event.pk)
    assert_lock_context(context)
    if locked.event_id != event.pk or locked.member_id and locked.member_id not in context.account_ids:
        raise EventInvalidTransition("Registration scope changed.")
    services = _boundary()
    if actor is not None:
        from .event_authority import require
        require(actor, event, "check_in")
    if source in FEATURE_SOURCES:
        event.makerspace = require_feature_locked(
            event.makerspace_id, "events.offline_checkin"
        )
    if source == EventCheckInEvent.Source.VENUE_STATION:
        credential = credential_for_event(event, lock=True, enabled=True)
        if credential is None or credential.version != station_version:
            raise PermissionDenied("Invalid station session.")
    operation_id = operation_id or uuid4()
    if EventCheckInEvent.objects.filter(
        makerspace_id=event.makerspace_id,
        operation_id=operation_id,
    ).exists():
        raise DuplicateCheckInOperation()
    from .hackathons.admission_lifecycle import require_attendance_mapping
    require_attendance_mapping(locked)
    if (
        locked.status != EventRegistration.Status.REGISTERED
        or event.status not in (Event.Status.PUBLISHED, Event.Status.COMPLETED)
    ):
        raise EventInvalidTransition("This registration cannot be marked attended.")

    occurred_at = attended_at or timezone.now()
    check_in = EventCheckInEvent(
        makerspace=event.makerspace,
        event=event,
        registration=locked,
        operation_id=operation_id,
        source=source,
        attended_at=occurred_at,
        actor=actor,
        session_id=session_id,
        station_version=station_version,
    )
    # The operation UUID is deployment-global, but validation must not query another
    # tenant to explain a collision. The database enforces uniqueness; the service maps
    # that race to the uniform idempotent outcome.
    check_in.full_clean(validate_unique=False)
    check_in.save()
    locked.status = EventRegistration.Status.ATTENDED
    locked.version += 1
    locked.save(update_fields=["status", "version"])
    from .hackathons.admission_lifecycle import attendance_changed_locked
    from .programme_locks import current_locks
    attendance_changed_locked(event=event, registration=locked, actor=actor, locks=current_locks(event.pk))
    services._audit(
        event,
        actor,
        "event.registration_attended",
        locked,
        {
            "registration_id": locked.pk,
            "check_in_event_id": check_in.pk,
            "source": source,
            "operation_id": str(operation_id),
            "reported_occurred_at": occurred_at.isoformat(),
            "recorded_at": check_in.recorded_at.isoformat(),
            "session_id": str(session_id) if session_id else None,
            "station_version": station_version,
        },
    )
    services.notify_event_lifecycle(event, "registration_attended", locked.pk)
    # Station sync always supplies a reported timestamp, even for live scans.
    # The bridge rechecks reported/recorded freshness and attendance after commit.
    if (source == EventCheckInEvent.Source.VENUE_STATION
            or (source == EventCheckInEvent.Source.QR and attended_at is None)):
        from apps.presence.event_attendance import event_attendance

        transaction.on_commit(lambda: event_attendance(locked), robust=True)
    return services._refresh(locked), check_in


def mark_attended(registration, **kwargs):
    updated, _check_in = mark_attended_with_event(registration, **kwargs)
    return updated

from django.utils.translation import gettext
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
            raise PermissionDenied(gettext("Invalid station session."))
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
    if locked.member_id:
        # A required stage form blocks attendance on every source, offline sync included;
        # a cached roster is never proof that the form was completed.
        from .staged_forms.admission_hooks import require_action_locked
        require_action_locked(event=event, member_id=locked.member_id, action="check_in")

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
    from .attendance_payout_bridge import attended_locked, publish_payout_eligibility_locked
    locked.save(update_fields=["status", "version", *attended_locked(locked)])
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
    publish_payout_eligibility_locked(event=event, registration=locked, actor=actor)
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


def pending_ticket_charge(registration):
    """Lane L6 (G33): the pending charge a ticket still owes -- its own, or its order's."""
    from apps.payments.models import Payment
    seat = getattr(registration, "order_seat", None)
    subject = ("event_order", seat.order_id) if seat is not None else ("event_registration", registration.pk)
    return Payment.objects.filter(makerspace_id=registration.event.makerspace_id, subject_type=subject[0],
                                  subject_id=subject[1], status=Payment.Status.PENDING).first()


def collect_at_desk(registration, *, actor, method="", reference="", received_at=None, terminal=False):
    """Take a pending ticket payment at the door: a receipt for cash/card, or a pay-now checkout.

    Money is recorded through the ledger's own seam (`reconcile_payments` writes the
    ManualSettlement receipt; the maker-checker rule still applies), so the desk needs
    RECORD_PAYMENT or Event Manager authority, like any settlement.
    """
    from apps.audit.services import record
    from apps.payments.models import Payment
    from apps.payments.reconciliation import reconcile_payments
    from .event_authority import require
    from .feature_gates import require_feature
    from .orders_errors import OrderRefused
    event = registration.event
    require(actor, event, "check_in")
    require_feature(event, "events.desk_collect")
    payment = pending_ticket_charge(registration)
    if payment is None:
        raise OrderRefused("nothing_to_collect", "This ticket has nothing left to pay.")
    if terminal:
        from apps.payments.services import create_checkout_url
        url = create_checkout_url(payment.pk, actor=actor)
        record(actor, "event.payment_collected_at_desk", makerspace=event.makerspace, target=registration,
               meta={"registration_id": registration.pk, "payment_id": payment.pk, "terminal": True, "method": ""})
        return {"payment": payment, "checkout_url": url}
    settlement = {"method": method, "reference": reference or "", "received_at": received_at or timezone.now()}
    result = reconcile_payments(actor=actor, makerspace_id=event.makerspace_id, payment_ids=[payment.pk],
                                target_status=Payment.Status.PAID_OFFLINE, settlement=settlement)[0]
    record(actor, "event.payment_collected_at_desk", makerspace=event.makerspace, target=registration,
           meta={"registration_id": registration.pk, "payment_id": payment.pk, "terminal": False, "method": method})
    return {"payment": result, "checkout_url": ""}

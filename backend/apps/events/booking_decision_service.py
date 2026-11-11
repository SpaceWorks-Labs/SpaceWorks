"""Transactional existing-booking venue decision; private implementation draft."""
from django.core.exceptions import ValidationError
from django.db import DatabaseError, IntegrityError
from rest_framework.exceptions import APIException, NotFound

from apps.accounts.loan_context_identity import borrower_aliases
from apps.audit.services import record
from apps.makerspaces.guards import require_module_locked
from apps.makerspaces.loan_context_generations import validate_generations
from .booking_decision_access import authorized_booking, authorized_event
from apps.separability.booking_decision_intent import canonical_intent, validate_intent
from .models_booking_decision import EventBookingDecision
from .services_write_boundary import write_boundary


class DecisionConflict(APIException):
    status_code = 409
    default_code = "decision_conflict"

    def __init__(self, code):
        super().__init__({"detail": "Booking decision cannot be applied.", "code": code})


class _Rediscover(Exception):
    pass


def _auth_original(actor, row):
    if row.creator_id is None:
        raise NotFound()
    if row.creator.account_purged_at is not None or row.creator.deletion_requested_at is not None:
        raise NotFound()
    try:
        if actor.pk not in borrower_aliases(row.creator):
            raise NotFound()
    except (ValueError, RuntimeError):
        raise NotFound() from None


def _observed(maker, operation_id):
    return EventBookingDecision.objects.filter(makerspace_id=maker.pk, operation_id=operation_id).values(
        "pk", "event_id", "booking_id", "creator_id").first()


def _fee_state(maker, event, *, lock=True):
    from apps.payments.models import Payment
    from .models import EventVenueFee
    fees = EventVenueFee.objects.filter(makerspace_id=maker.pk, event_id=event.pk)
    if lock:
        fees = fees.select_for_update(nowait=True, of=("self",))
    fee = fees.first()
    if fee is not None and Payment.objects.filter(
            makerspace_id=maker.pk, subject_type="event_venue_fee", subject_id=fee.pk).exists():
        return "historical_debt"
    from .venue_fee_history import history_state
    history = history_state(maker.pk, event.pk)
    if history != "none":
        return history
    if fee is None:
        return "none"
    return "free_no_debt" if fee.status == EventVenueFee.Status.FREE else "configured"


def _covers(event, booking):
    return booking.starts_at <= event.starts_at and event.ends_at <= booking.ends_at


def _refuse_out_of_service(room, event):
    """A room under a BLOCK-mode outage during the event's time cannot newly host it.

    The same admission seam a new booking meets (`bookings.admission._refuse_room_outage`);
    a warn-mode outage still links and is shown as a conflict on the venue panel.
    """
    from types import SimpleNamespace
    from apps.bookings.admission import _refuse_room_outage
    from apps.bookings.exceptions import BookingConflict
    try:
        _refuse_room_outage(room, SimpleNamespace(starts_at=event.starts_at, ends_at=event.ends_at))
    except BookingConflict:
        raise DecisionConflict("room_out_of_service") from None


def create_decision(actor, maker, event_id, *, booking_id, operation_id, expected_generation,
                    expected_revision, expected_events_epoch, expected_bookings_epoch,
                    allow_partial_coverage=False):
    for attempt in range(2):
        try:
            return _create_once(actor, maker, event_id, booking_id=booking_id, operation_id=operation_id,
                expected_generation=expected_generation, expected_revision=expected_revision,
                expected_events_epoch=expected_events_epoch, expected_bookings_epoch=expected_bookings_epoch,
                allow_partial_coverage=allow_partial_coverage)
        except (_Rediscover, IntegrityError):
            if attempt:
                raise DecisionConflict("lock_busy") from None
        except DatabaseError as exc:
            if getattr(exc.__cause__, "sqlstate", None) in {"55P03", "40P01"}:
                raise DecisionConflict("lock_busy") from None
            raise
    raise DecisionConflict("lock_busy")


def _create_once(actor, maker, event_id, *, booking_id, operation_id, expected_generation,
                 expected_revision, expected_events_epoch, expected_bookings_epoch,
                 allow_partial_coverage=False):
    event = authorized_event(actor, maker, event_id)
    authorized_booking(actor, maker, booking_id)
    observed = _observed(maker, operation_id)
    if observed:
        authorized_event(actor, maker, observed["event_id"])
        if observed["booking_id"] is None:
            raise NotFound()
        authorized_booking(actor, maker, observed["booking_id"])
    additional = (observed["event_id"],) if observed else ()
    with write_boundary(event, actor=actor, nowait_makerspaces=True, additional_event_ids=additional):
        from apps.accounts.claim_sessions import carry_claim_context
        from apps.accounts.models import User
        from apps.bookings.models import BookableSpace, Booking
        from apps.makerspaces.models import Makerspace
        fresh = carry_claim_context(actor, User.objects.filter(pk=actor.pk).first())
        if fresh is None:
            raise NotFound()
        maker = Makerspace.objects.get(pk=maker.pk)
        require_module_locked(maker, "events")
        require_module_locked(maker, "bookings")
        event = authorized_event(fresh, maker, event_id)
        current = _observed(maker, operation_id)
        if current != observed:
            raise _Rediscover()
        booking_ids = {booking_id} | ({current["booking_id"]} if current else set())
        if None in booking_ids:
            raise NotFound()
        space_ids = set(Booking.objects.filter(pk__in=booking_ids).values_list("space_id", flat=True))
        spaces = {row.pk: row for row in BookableSpace.objects.select_for_update(nowait=True, of=("self",))
                  .filter(pk__in=space_ids).order_by("pk")}
        locked = {row.pk: row for row in Booking.objects.select_for_update(nowait=True, of=("self",))
                  .filter(pk__in=booking_ids).order_by("pk")}
        if set(locked) != booking_ids or any(row.space_id not in spaces for row in locked.values()):
            raise NotFound()
        authorized_booking(fresh, maker, booking_id)
        if current:
            authorized_event(fresh, maker, current["event_id"])
            authorized_booking(fresh, maker, current["booking_id"])
            row = EventBookingDecision.objects.select_for_update(nowait=True, of=("self",)).get(pk=current["pk"])
            _auth_original(fresh, row)
            try:
                stored = validate_intent(row.intent)
            except (ValidationError, ValueError, TypeError):
                raise NotFound() from None
            candidate = canonical_intent(makerspace_id=maker.pk, event_id=event_id, booking_id=booking_id,
                                         creator_id=row.creator_id)
            if stored != candidate or row.event_id != event_id or row.booking_id != booking_id:
                raise DecisionConflict("operation_conflict")
            return row, True
        validate_generations(maker.loan_context_generations)
        if (expected_generation is not None or expected_revision != 0
                or maker.loan_context_generations["events"] != str(expected_events_epoch)
                or maker.loan_context_generations["bookings"] != str(expected_bookings_epoch)):
            raise DecisionConflict("stale_context")
        if EventBookingDecision.objects.filter(event_id=event_id).exists() or EventBookingDecision.objects.filter(booking_id=booking_id).exists():
            raise DecisionConflict("operation_conflict")
        if locked[booking_id].replaces_id is not None:
            # A replacement already belongs to another event's retained chain (decision 216).
            raise DecisionConflict("operation_conflict")
        room = spaces[locked[booking_id].space_id]
        if (event.status not in (event.Status.DRAFT, event.Status.PUBLISHED)
                or not room.is_active or room.kind == BookableSpace.Kind.MACHINE or room.machine_id is not None
                or locked[booking_id].status not in (Booking.Status.PENDING, Booking.Status.CONFIRMED)):
            raise NotFound()
        _refuse_out_of_service(room, event)
        partial = not _covers(event, locked[booking_id])
        if partial and not allow_partial_coverage:  # decision 223 G4: the booking must hold the event's times
            raise DecisionConflict("booking_does_not_cover_event")
        state = _fee_state(maker, event)
        if state in {"historical_debt", "unresolved"}:
            raise DecisionConflict("venue_debt_history_requires_review")
        if state == "configured":
            raise DecisionConflict("venue_fee_unresolved")
        row = EventBookingDecision.objects.create(makerspace=maker, event=event, booking=locked[booking_id],
            creator=fresh, operation_id=operation_id, intent=canonical_intent(makerspace_id=maker.pk,
                event_id=event_id, booking_id=booking_id, creator_id=fresh.pk))
        record(fresh, "event.booking_decision_linked", makerspace=maker, target=event,
               meta={"domain": "booking", "operation": "linked"})
        if partial:
            record(fresh, "event.booking_decision_partial_coverage", makerspace=maker, target=event,
                   meta={"domain": "booking", "operation": "partial_coverage"})
        from apps.integrations.link_webhooks import link_webhook
        link_webhook(maker, "event_booking_linked", event_id=event.pk, booking_id=booking_id)
        return row, False

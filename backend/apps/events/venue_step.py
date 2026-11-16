"""Create an event and request or link its room in one flow (decision 223 G6).

The organizer's "room step" at event creation. The event is created first as an ordinary DRAFT
(`services.create_event`); then ONE of four room modes runs against it:

* `request` -- the actor books the room for themselves (a member requesting the venue); an
  approval-mode room goes PENDING and holds its slot tentatively (`events.venue_holds`);
* `book`    -- staff with `manage_reservations` book it for an active member (`member_id`);
* `house`   -- staff book a house booking: no member booker, no charge, no plan hours (#223 (h));
* `link`    -- staff link an EXISTING booking through the ordinary decision service (needs both
  tenant-wide roles, and the booking must cover the event window).

The booking and the event live in separate transactions (the decision service refuses to nest).
If the room step fails the event is KEPT as a draft (nothing is published or charged) and the
result names the failure so the organizer can retry from the panel; a booking created by this
call that could not be linked is cancelled again, best effort. The availability the UI shows
before this call is `GET admin/makerspace/<id>/spaces/<space>/bookings/availability/`.
"""

from uuid import uuid4

from django.core.exceptions import ValidationError as DjangoValidationError
from django.http import Http404
from rest_framework.exceptions import APIException

from apps.audit.services import record
from apps.bookings.exceptions import BookingConflict, BookingInvalidTransition

MODES = ("request", "book", "house", "link")


def _code(exc):
    detail = getattr(exc, "detail", None)
    if isinstance(detail, dict) and isinstance(detail.get("code"), str):
        return detail["code"]
    if isinstance(exc, BookingConflict):
        return "room_unavailable"
    if isinstance(exc, BookingInvalidTransition):
        return "room_invalid"
    if isinstance(exc, Http404):
        return "not_found"
    return getattr(exc, "default_code", "room_step_failed")


def _space(actor, maker, space_id, *, manage):
    from rest_framework.exceptions import NotFound
    from apps.bookings.booking_authority import get_space
    from apps.bookings.models import BookableSpace
    if manage:
        space = get_space(actor, space_id, "manage_reservations")
    else:
        space = BookableSpace.objects.select_related("makerspace").filter(pk=space_id, is_active=True).first()
    if (space is None or space.makerspace_id != maker.pk or space.kind == BookableSpace.Kind.MACHINE
            or space.machine_id is not None):
        raise NotFound()
    return space


def _booking_for(actor, maker, event, room):
    from apps.bookings import services as booking_services
    mode = room["mode"]
    window = {"starts_at": event.starts_at, "ends_at": event.ends_at, "note": room.get("note", "")}
    if mode == "request":
        return booking_services.create_booking(_space(actor, maker, room["space_id"], manage=False),
                                               member=actor, actor=actor, **window)
    space = _space(actor, maker, room["space_id"], manage=True)
    if mode == "house":
        return booking_services.create_booking(space, actor=actor, house=True, **window)
    from django.shortcuts import get_object_or_404
    from apps.bookings.views_admin_booking_create import _members
    from apps.presence.guard import require_active_member
    membership = get_object_or_404(_members(actor, space), user_id=room["member_id"])
    require_active_member(membership.user, maker)
    return booking_services.create_booking(space, member=membership.user, actor=actor,
                                           price_confirmation=room.get("price_confirmation"), **window)


def _link_new(actor, maker, event, booking):
    """Link the booking this call just made. The event is brand new and the booking covers it exactly."""
    from apps.integrations.link_webhooks import link_webhook
    from apps.separability.booking_decision_intent import canonical_intent
    from .models_booking_decision import EventBookingDecision
    from .services_write_boundary import write_boundary
    with write_boundary(event, actor=actor):
        EventBookingDecision.objects.create(
            makerspace=maker, event=event, booking=booking, creator=actor, operation_id=uuid4(),
            intent=canonical_intent(makerspace_id=maker.pk, event_id=event.pk, booking_id=booking.pk,
                                    creator_id=actor.pk))
        record(actor, "event.booking_decision_linked", makerspace=maker, target=event,
               meta={"domain": "booking", "operation": "linked"})
        link_webhook(maker, "event_booking_linked", event_id=event.pk, booking_id=booking.pk)


def _undo(actor, booking):
    """Best effort: a booking this call created but could not link must not keep holding the room."""
    from apps.bookings import services as booking_services
    for member_cancel in (False, True):
        try:
            booking_services.cancel_booking(booking, actor=actor, member_cancel=member_cancel,
                                            reason="Event creation failed")
            return None
        except Exception:
            continue
    return booking.pk


def _link_existing(actor, maker, event, room):
    from .booking_decision_service import create_decision
    maker.refresh_from_db(fields=["loan_context_generations"])
    gens = maker.loan_context_generations
    create_decision(actor, maker, event.pk, booking_id=room["booking_id"], operation_id=uuid4(),
                    expected_generation=None, expected_revision=0, expected_events_epoch=gens["events"],
                    expected_bookings_epoch=gens["bookings"])
    return room["booking_id"]


def run_room_step(actor, maker, event, room):
    """Apply the room mode to a just-created event. Returns the `room` result dict; never raises."""
    from apps.makerspaces.guards import require_module
    result = {"mode": room["mode"], "status": "linked", "booking_id": None, "booking_status": None}
    created = None
    try:
        require_module(maker, "bookings")
        if room["mode"] == "link":
            result["booking_id"] = _link_existing(actor, maker, event, room)
        else:
            created = _booking_for(actor, maker, event, room)
            _link_new(actor, maker, event, created)
            result["booking_id"], result["booking_status"] = created.pk, created.status
    except (APIException, BookingConflict, BookingInvalidTransition, DjangoValidationError, Http404) as exc:
        result.update(status="failed", code=_code(exc), detail=str(getattr(exc, "detail", exc))[:300])
        if created is not None:
            result["orphan_booking_id"] = _undo(actor, created)
            result["booking_id"] = None
        return result
    record(actor, "event.created_with_room", makerspace=maker, target=event,
           meta={"mode": room["mode"], "booking_id": result["booking_id"]})
    return result

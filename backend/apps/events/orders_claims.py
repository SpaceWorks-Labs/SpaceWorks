"""Claiming a seat: the only way an order seat becomes a registration (release 2 L6, G27).

The attendee signs in -- with the email address the seat names, verified -- and presents
the claim token from their invite. The seat then becomes their registration through the
ordinary `register()` service (audience, form answers, waivers, duplicates, credentials,
calendar and notices all apply), inside `orders_context.filling_seat`, so it carries no
charge of its own and keeps the ticket type the buyer paid for. Nobody is ever
registered without an account (#71).
"""

from django.utils.translation import gettext
from django.utils import timezone

from apps.audit.services import record

from .exceptions import DuplicateRegistration
from .models import EventOrder, EventOrderSeat
from .orders_attendees import token_digest
from .orders_context import filling_seat
from .orders_errors import OrderRefused
from .services_write_boundary import event_write

REGISTRATION_KEYS = ("custom_answers", "form_payload", "host_waiver_id", "host_waiver_version",
                     "host_waiver_accepted", "inline_forms")


def fill_seat(seat, *, member, actor, **values):
    """Turn a locked, unclaimed, paid seat into `member`'s registration (caller holds the boundary)."""
    import secrets
    from .services_registration import register
    # of=("self",): line.ticket_type is nullable, and Postgres refuses FOR UPDATE across an outer join.
    seat = (EventOrderSeat.objects.select_for_update(of=("self",)).select_related("order", "line__ticket_type")
            .get(pk=seat.pk))
    if seat.status != EventOrderSeat.Status.UNCLAIMED or seat.order.status != EventOrder.Status.PAID:
        raise OrderRefused("claim_invalid", gettext("This place has already been claimed or was cancelled."))
    with filling_seat(seat):
        try:
            registration = register(seat.event, member=member, actor=actor,
                                    ticket_type_id=seat.line.ticket_type_id,
                                    **{key: values[key] for key in REGISTRATION_KEYS if key in values})
        except DuplicateRegistration:
            raise OrderRefused("already_registered", gettext("You already have a place at this event.")) from None
    seat.registration, seat.status, seat.claimed_at = registration, EventOrderSeat.Status.CLAIMED, timezone.now()
    seat.attendee_email = (member.email or seat.attendee_email).strip().lower()
    seat.claim_token_digest = secrets.token_hex(32)
    seat.save(update_fields=["registration", "status", "claimed_at", "attendee_email", "claim_token_digest"])
    record(actor, "event.seat_claimed", makerspace=seat.makerspace, target=seat.order,
           meta={"order_id": seat.order_id, "seat_id": seat.pk, "registration_id": registration.pk})
    return registration


def find_claim(token):
    seat = (EventOrderSeat.objects.select_related("order__buyer", "event__makerspace", "line__ticket_type")
            .filter(claim_token_digest=token_digest(token), status=EventOrderSeat.Status.UNCLAIMED,
                    order__status=EventOrder.Status.PAID).first() if token and len(str(token)) <= 128 else None)
    if seat is None or not seat.attendee_email:
        raise OrderRefused("claim_invalid", gettext("This claim link is not valid any more."))
    return seat


def require_claimant(seat, user):
    email = (user.email or "").strip().lower()
    if not email or email != seat.attendee_email.strip().lower() or not getattr(user, "email_verified_at", None):
        raise OrderRefused("claim_email_mismatch",
                           gettext("Sign in with the verified email address this ticket was sent to."))


def claim(token, *, user, values=None):
    seat = find_claim(token)
    require_claimant(seat, user)
    return _claim(seat.event, member=user, actor=user, seat_id=seat.pk, values=values or {})


@event_write
def _claim(event, *, member, actor, seat_id, values):
    from .feature_gates import require_feature
    require_feature(event, "events.orders")
    seat = EventOrderSeat.objects.get(pk=seat_id, event=event)
    return fill_seat(seat, member=member, actor=actor, **values)


def claim_own_seat(order, seat_id, *, member, values=None):
    """The buyer claims their own seat after paying (an event with a form or waiver)."""
    seat = EventOrderSeat.objects.select_related("order").filter(pk=seat_id, order=order, order__buyer=member).first()
    if seat is None:
        raise OrderRefused("claim_invalid", gettext("That seat is not yours to claim."))
    require_claimant(seat, member)
    return _claim(seat.event, member=member, actor=member, seat_id=seat.pk, values=values or {})

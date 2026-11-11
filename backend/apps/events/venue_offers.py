"""Offers after an event is cancelled or moved (decision 223 (m)); they NEVER act.

Decision 216 keeps the event and its booking independent: the link must not move money or time
on its own. So a cancel or a move returns a list of OFFERS, each naming an action the caller
may take next through the booking's or the fee's own endpoint (their own refund cases, repricing
and approval apply). Nothing here writes. Each offer says whether THIS actor may take it
(`allowed`): a Space Manager may cancel the room, an Event Manager without room authority is
told to ask one.

* `cancel_booking`   -- the event was cancelled and its room reservation is still live;
* `move_booking`     -- the event window changed and the reservation no longer covers it;
* `change_venue_fee` -- a legacy venue fee exists (configured or charged) for a cancelled or moved event.
"""

from rest_framework import serializers

from .venue_state import bookings_apply, coverage, current_booking

LIVE = ("pending", "confirmed")


class VenueOfferSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=["cancel_booking", "move_booking", "change_venue_fee"])
    booking_id = serializers.IntegerField(allow_null=True)
    route = serializers.CharField(help_text="Name of the existing endpoint that performs it.")
    allowed = serializers.BooleanField(help_text="Whether this actor may take the action.")
    proposed_window = serializers.JSONField(required=False, allow_null=True)
    fee_status = serializers.CharField(required=False, allow_null=True)


def _may_manage_room(actor, booking):
    from apps.bookings import booking_authority, booking_permissions
    return booking_authority.can(actor, booking.space, booking_permissions.MANAGE_RESERVATIONS)


def _may_move_room(actor, booking):
    """Moving a booking is a staff tool: the offer is only actionable while `bookings.staff_tools` is on (m22)."""
    from apps.makerspaces.platform import feature_enabled
    return feature_enabled(booking.space.makerspace, "bookings.staff_tools") and _may_manage_room(actor, booking)


def _fee_offer(actor, event):
    from apps.accounts import rbac
    from .models import EventVenueFee
    fee = EventVenueFee.objects.filter(event=event).exclude(status=EventVenueFee.Status.FREE).first()
    if fee is None:
        return None
    return {"action": "change_venue_fee", "booking_id": None, "route": "admin-event-venue-fee",
            "allowed": rbac.can(actor, rbac.Action.MANAGE_EVENTS, event.makerspace_id),
            "proposed_window": None, "fee_status": fee.status}


def venue_offers(actor, event):
    """The offers for the event's CURRENT state; empty when nothing is linked or Bookings is off."""
    offers = []
    if bookings_apply(event):
        _decision, booking = current_booking(event)
        if booking is not None and booking.status in LIVE:
            if event.status == "cancelled":
                offers.append({"action": "cancel_booking", "booking_id": booking.pk, "route": "admin-booking-cancel",
                               "allowed": _may_manage_room(actor, booking), "proposed_window": None,
                               "fee_status": None})
            elif coverage(event, booking) == "not_covered":
                offers.append({"action": "move_booking", "booking_id": booking.pk, "route": "admin-booking-time-edit",
                               "allowed": _may_move_room(actor, booking),
                               "proposed_window": {"starts_at": event.starts_at, "ends_at": event.ends_at},
                               "fee_status": None})
    fee = _fee_offer(actor, event)
    if fee is not None and (event.status == "cancelled" or offers):
        offers.append(fee)
    return offers

"""The "this registration fills a paid order seat" context (release 2 L6).

An order seat becomes a registration through the ordinary `register()` service, so every
admission rule (audience, forms, waivers, duplicates, credentials, calendar, notices)
still applies. Inside this context, and only here, four things differ because the seat
was already sold:

* the registration carries no charge of its own -- the order's `Payment` holds the money
  (`service_payments.member_price` quotes 0);
* the ticket is the seat's own ticket type, whatever its sales window, tier or hidden
  flag says now (`ticketing.select_ticket`);
* registration stays open until the event ends, past the signup cutoff
  (`capacity.registration_is_open`);
* the seat itself is not counted as held while it turns into this registration
  (`capacity.held_seats`).
"""

from contextlib import contextmanager
from contextvars import ContextVar

_seat = ContextVar("event_order_seat", default=None)


@contextmanager
def filling_seat(seat):
    token = _seat.set(seat)
    try:
        yield seat
    finally:
        _seat.reset(token)


def current_seat():
    return _seat.get()


def claiming_seat_id():
    seat = _seat.get()
    return seat.pk if seat is not None else None


def seat_ticket(event):
    """The seat's own ticket type when filling a seat of this event, else None."""
    seat = _seat.get()
    if seat is None or seat.event_id != event.pk:
        return None
    return seat.line.ticket_type

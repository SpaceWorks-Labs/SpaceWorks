"""#184 matrix, bookings and events: bookings, registrations, ticket/add-on orders and venue fees (G6)."""

from decimal import Decimal

import pytest

from apps.bookings.models import Booking
from apps.events import services as event_services
from apps.events.models import EventOrder, EventRegistration, EventVenueFee
from tests.money_modes.helpers import FREE, MODES, ONLINE, assert_mode_outcome, charges, fake_provider, set_mode
from tests.payments.test_track3_booking_event_charging import (
    bookable, create_booking, member_with_phone, published_event,
)
from tests.return_helpers import make_member, make_space

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("mode", MODES)
def test_a_paid_room_books_in_every_mode(mode, monkeypatch, django_capture_on_commit_callbacks):
    space = set_mode(make_space(f"mm-book-{mode}"), "bookings", mode, extra_modules=("bookings",))
    checkout = fake_provider(monkeypatch) if mode == ONLINE else None
    member = member_with_phone(f"mm-book-{mode}-m", space)
    with django_capture_on_commit_callbacks(execute=True):
        booking = create_booking(bookable(space, amount="12.50"), member, actor=None)
    assert booking.status == Booking.Status.CONFIRMED
    payment = assert_mode_outcome(mode, charges(space, "booking"), checkout)
    assert payment is None or payment.amount == Decimal("12.50")


@pytest.mark.parametrize("mode", MODES)
def test_a_paid_event_registers_in_every_mode(mode, monkeypatch, django_capture_on_commit_callbacks):
    space = set_mode(make_space(f"mm-reg-{mode}"), "events", mode, extra_modules=("events",))
    checkout = fake_provider(monkeypatch) if mode == ONLINE else None
    event = published_event(space, make_member(f"mm-reg-{mode}-sm", space), amount="8.00")
    with django_capture_on_commit_callbacks(execute=True):
        registration = event_services.register(event, member=member_with_phone(f"mm-reg-{mode}-m", space), actor=None)
    assert registration.status == EventRegistration.Status.REGISTERED
    assert_mode_outcome(mode, charges(space, "event_registration"), checkout)


@pytest.mark.parametrize("mode", MODES)
def test_ticket_and_add_on_orders_complete_in_every_mode(mode, monkeypatch, django_capture_on_commit_callbacks):
    from apps.events.addons import create_addon
    from tests.events.orders_helpers import l6_space, place, quote, ticketed_event, verified
    space = set_mode(l6_space(f"mm-order-{mode}"), "events", mode)
    checkout = fake_provider(monkeypatch) if mode == ONLINE else None
    _space, event, staff, ticket = ticketed_event(space, amount=10)
    shirt = create_addon(event, actor=staff, name="T-shirt", kind="merch", amount=Decimal(15), stock=10)
    buyer = verified(f"mm-order-{mode}-buyer")
    body = {"addons": [{"addon_id": shirt.pk, "quantity": 1}]}
    quoted = quote(buyer, event, [{"ticket_type_id": ticket.pk, "quantity": 2}], **body)
    assert quoted.status_code == 200, quoted.data
    with django_capture_on_commit_callbacks(execute=True):
        placed = place(buyer, event, [{"ticket_type_id": ticket.pk, "quantity": 2}], **body)
    assert placed.status_code == 201, placed.data
    order = EventOrder.objects.get(buyer=buyer)
    if mode == FREE:
        # G6: the order is free and seated at once -- never refused as `order_not_payable`.
        assert order.total == Decimal("0") and order.status == EventOrder.Status.PAID
        assert order.pricing_snapshot["notes"] == ["charges_off"]
        assert all(line.unit_amount == 0 and line.line_total == 0 for line in order.lines.all())
    else:
        assert order.total == Decimal("35.00") and order.status == EventOrder.Status.PENDING
    assert_mode_outcome(mode, charges(space, "event_order"), checkout)


@pytest.mark.parametrize("mode", MODES)
def test_a_venue_fee_resolves_in_every_mode(mode, monkeypatch, django_capture_on_commit_callbacks):
    from apps.events.venue_fees import charge, configure
    from tests.events.orders_helpers import l6_space, ticketed_event, verified
    space = set_mode(l6_space(f"mm-venue-{mode}"), "events", mode)
    checkout = fake_provider(monkeypatch) if mode == ONLINE else None
    _space, event, staff, _ticket = ticketed_event(space)
    payer = verified(f"mm-venue-{mode}-payer")
    configure(event, actor=staff, payer=payer, mode=EventVenueFee.Mode.CUSTOM, basis=EventVenueFee.Basis.FLAT,
              amount=Decimal("100.00"))
    with django_capture_on_commit_callbacks(execute=True):
        fee, payment = charge(event, actor=staff)
    if mode == FREE:
        assert payment is None and fee.status == EventVenueFee.Status.FREE
        assert charges(space, "event_venue_fee") == []
        return
    assert fee.status == EventVenueFee.Status.CHARGED and payment.status == "pending"
    assert charges(space, "event_venue_fee") == [payment]
    # The payer opens the hosted checkout from their payments page; the rail is there only online.
    from apps.payments.availability import online_payments_enabled_for
    assert online_payments_enabled_for(payment) is (mode == ONLINE)
    assert checkout is None or not checkout.called

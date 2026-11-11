"""L6 G32: ticket-type change pays the difference or opens a staff-approved refund case."""

from decimal import Decimal

import pytest
from django.urls import reverse

from apps.events.models import EventOrder
from apps.events.orders_pricing import paid_ticket_price
from apps.events.ticketing import create_ticket
from apps.payments.models import Payment, RefundCase
from tests.events.collab_helpers import client_for
from tests.events.orders_helpers import order_payment, place, settings_for, settle_offline, ticketed_event, verified

pytestmark = pytest.mark.django_db


def _change(user, registration, ticket):
    return client_for(user).post(reverse("member-ticket-change-type", kwargs={
        "makerspace_id": registration.event.makerspace_id, "pk": registration.pk}),
        {"ticket_type_id": ticket.pk}, format="json")


def _bought(django_capture_on_commit_callbacks, amount=10):
    space, event, staff, ticket = ticketed_event(amount=amount)
    settings_for(event, type_changes_allowed=True)
    buyer = verified("buyer")
    place(buyer, event, [{"ticket_type_id": ticket.pk, "quantity": 1}])
    with django_capture_on_commit_callbacks(execute=True):
        settle_offline(order_payment(EventOrder.objects.get()), staff)
    return event, staff, buyer, buyer.event_registrations.get()


def test_cheaper_type_switches_now_and_opens_refund_case(django_capture_on_commit_callbacks):
    event, staff, buyer, registration = _bought(django_capture_on_commit_callbacks)
    cheaper = create_ticket(event, actor=staff, name="Student", amount=Decimal(4))
    assert paid_ticket_price(registration)[0] == Decimal("10.00")
    response = _change(buyer, registration, cheaper)
    assert response.status_code == 200 and response.data["status"] == "changed"
    registration.refresh_from_db()
    assert registration.ticket_type == cheaper
    case = RefundCase.objects.get()
    assert case.due_amount == Decimal("6.00") and case.status == "open"
    assert paid_ticket_price(registration)[0] == Decimal("4.00")


def test_dearer_type_needs_a_paid_difference(django_capture_on_commit_callbacks):
    event, staff, buyer, registration = _bought(django_capture_on_commit_callbacks)
    vip = create_ticket(event, actor=staff, name="VIP", amount=Decimal(25))
    response = _change(buyer, registration, vip)
    assert response.status_code == 200 and response.data["status"] == "payment_required"
    change = EventOrder.objects.get(kind="type_change")
    payment = Payment.objects.get(subject_type="event_order", subject_id=change.pk)
    assert payment.amount == Decimal("15.00")
    registration.refresh_from_db()
    assert registration.ticket_type != vip
    with django_capture_on_commit_callbacks(execute=True):
        settle_offline(payment, staff)
    registration.refresh_from_db()
    assert registration.ticket_type == vip
    assert paid_ticket_price(registration)[0] == Decimal("25.00")


def test_type_change_refused_when_not_allowed(django_capture_on_commit_callbacks):
    event, staff, buyer, registration = _bought(django_capture_on_commit_callbacks)
    settings_for(event, type_changes_allowed=False)
    other = create_ticket(event, actor=staff, name="Other", amount=Decimal(10))
    assert _change(buyer, registration, other).data["code"] == "transfer_not_allowed"

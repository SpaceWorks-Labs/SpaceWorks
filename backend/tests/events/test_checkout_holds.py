"""L6 G28: seat holds never oversell; expiry releases seats; no hold means seat-at-payment."""

from datetime import timedelta

import pytest
from django.utils import timezone

from apps.events.models import EventCheckoutHold, EventOrder
from apps.events.reminders_payments import sweep_order_checkouts_task
from apps.payments.models import RefundCase
from tests.events.orders_helpers import (
    l6_space, order_payment, place, settle_offline, ticketed_event, verified,
)

pytestmark = pytest.mark.django_db


def test_two_buyers_cannot_hold_more_seats_than_exist():
    space, event, _staff, ticket = ticketed_event(amount=10, capacity=3)
    first, second = verified("first"), verified("second")
    assert place(first, event, [{"ticket_type_id": ticket.pk, "quantity": 2}]).status_code == 201
    refused = place(second, event, [{"ticket_type_id": ticket.pk, "quantity": 2}])
    assert refused.status_code == 409 and refused.data["code"] == "sold_out"
    assert place(second, event, [{"ticket_type_id": ticket.pk, "quantity": 1}]).status_code == 201
    assert place(verified("third"), event, [{"ticket_type_id": ticket.pk, "quantity": 1}]).data["code"] == "sold_out"


def test_expired_hold_releases_seats_and_voids_the_charge(django_capture_on_commit_callbacks):
    space, event, _staff, ticket = ticketed_event(amount=10, capacity=1)
    buyer = verified("buyer")
    place(buyer, event, [{"ticket_type_id": ticket.pk, "quantity": 1}])
    order = EventOrder.objects.get()
    EventCheckoutHold.objects.filter(order=order).update(expires_at=timezone.now() - timedelta(seconds=1))
    with django_capture_on_commit_callbacks(execute=True):
        sweep_order_checkouts_task()
    order.refresh_from_db()
    assert order.status == "expired"
    assert order.hold.release_reason == "expired"
    assert order_payment(order).status == "canceled"
    assert place(verified("next"), event, [{"ticket_type_id": ticket.pk, "quantity": 1}]).status_code == 201


def test_without_holds_a_late_payment_for_a_full_event_is_refunded_by_staff(django_capture_on_commit_callbacks):
    space = l6_space(features=["events.orders"])
    _space, event, staff, ticket = ticketed_event(space, amount=10, capacity=1)
    late, quick = verified("late"), verified("quick")
    place(late, event, [{"ticket_type_id": ticket.pk, "quantity": 1}])
    place(quick, event, [{"ticket_type_id": ticket.pk, "quantity": 1}])
    late_order, quick_order = EventOrder.objects.get(buyer=late), EventOrder.objects.get(buyer=quick)
    assert not EventCheckoutHold.objects.exists()
    with django_capture_on_commit_callbacks(execute=True):
        settle_offline(order_payment(quick_order), staff)
    with django_capture_on_commit_callbacks(execute=True):
        settle_offline(order_payment(late_order), staff)
    late_order.refresh_from_db()
    assert late_order.status == "unfulfilled"
    case = RefundCase.objects.get(payment=order_payment(late_order))
    assert case.status == "open" and case.due_amount == 10 and case.refund is None
    assert event.registrations.filter(status="registered").count() == 1


def test_buyer_abandons_an_unpaid_order():
    from django.urls import reverse
    from tests.events.collab_helpers import client_for
    space, event, _staff, ticket = ticketed_event(amount=10)
    buyer = verified("buyer")
    place(buyer, event, [{"ticket_type_id": ticket.pk, "quantity": 1}])
    order = EventOrder.objects.get()
    response = client_for(buyer).post(reverse("member-order-cancel", kwargs={
        "makerspace_id": space.pk, "order_id": order.pk}), {}, format="json")
    assert response.status_code == 200 and response.data["status"] == "cancelled"
    assert order_payment(order).status == "canceled"

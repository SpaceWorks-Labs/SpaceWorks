"""L6 G34: a per-event refund policy override that may only become more generous after the first sale."""

from datetime import timedelta
from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.events.models import EventOrder
from apps.payments.models import RefundPolicy
from apps.payments.refund_policy import assess
from tests.events.collab_helpers import client_for
from tests.events.orders_helpers import order_payment, place, settle_offline, ticketed_event, verified

pytestmark = pytest.mark.django_db

POLICY = {"enabled": True, "full_before_minutes": 1440, "partial_before_minutes": 60, "partial_percent": 50,
          "cancellation_fee": "0.00", "policy_text": "Full refund up to a day before."}


def _set(staff, event, **values):
    return client_for(staff).post(reverse("admin-event-refund-policy", kwargs={"pk": event.pk}),
                                  {**POLICY, **values}, format="json")


def test_override_applies_and_locks_after_first_sale(django_capture_on_commit_callbacks):
    space, event, staff, ticket = ticketed_event(amount=20)
    RefundPolicy.objects.create(makerspace=space, area="events", full_before_minutes=10, partial_before_minutes=0)
    assert _set(staff, event).status_code == 200
    assert _set(staff, event, full_before_minutes=2000).status_code == 200  # stricter is fine before any sale
    assert _set(staff, event).status_code == 200
    buyer = verified("buyer")
    place(buyer, event, [{"ticket_type_id": ticket.pk, "quantity": 1}])
    payment = order_payment(EventOrder.objects.get())
    with django_capture_on_commit_callbacks(execute=True):
        settle_offline(payment, staff)
    stricter = _set(staff, event, partial_percent=20)
    assert stricter.status_code == 409 and stricter.data["code"] == "policy_less_generous"
    assert _set(staff, event, partial_percent=80).status_code == 200
    payment.refresh_from_db()
    due, snapshot = assess(payment, reason_code="registration_cancelled",
                           cancelled_at=event.starts_at - timedelta(minutes=120))
    assert snapshot["band"] == "partial" and due == Decimal("16.00")
    shown = client_for(verified("visitor")).get(reverse("public-event-ticket-shop", kwargs={
        "makerspace_slug": space.slug, "public_token": event.public_token}))
    assert shown.data["policy"]["text"] == POLICY["policy_text"] and shown.data["policy"]["overridden"] is True
    assert _set(staff, event, enabled=False).data["code"] == "policy_less_generous"


def test_organiser_without_manage_events_cannot_override():
    space, event, staff, _ticket = ticketed_event(amount=20)
    outsider = verified("outsider")
    assert _set(outsider, event).status_code in (403, 404)
    assert timezone.now() < event.starts_at

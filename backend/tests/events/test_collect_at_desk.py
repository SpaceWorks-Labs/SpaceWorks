"""L6 G33: collect a pending ticket payment at the desk (receipt), and the Add-guest pay link."""

import pytest
from django.urls import reverse

from apps.payments.models import ManualSettlement, Payment
from tests.events.collab_helpers import client_for
from tests.events.orders_helpers import l6_space, ticketed_event, verified
from tests.events.ticketing_helpers import signup

pytestmark = pytest.mark.django_db


def _pending(space=None):
    space, event, staff, ticket = ticketed_event(space, amount=15)
    guest = verified("guest")
    assert signup(event, guest, ticket_type_id=ticket.pk).status_code == 201
    return event, staff, guest.event_registrations.get()


def _collect(staff, registration, body):
    return client_for(staff).post(reverse("admin-event-registration-collect-payment", kwargs={"pk": registration.pk}),
                                  body, format="json")


def test_desk_records_a_cash_receipt():
    event, staff, registration = _pending()
    assert _collect(staff, registration, {}).status_code == 400  # a receipt needs its method
    response = _collect(staff, registration, {"method": "cash"})
    assert response.status_code == 200, response.data
    payment = Payment.objects.get(subject_type="event_registration", subject_id=registration.pk)
    assert payment.status == "paid_offline" and ManualSettlement.objects.filter(payment=payment).exists()
    again = _collect(staff, registration, {"method": "cash"})
    assert again.status_code == 409 and again.data["code"] == "nothing_to_collect"


def test_desk_collect_switch_off():
    event, staff, registration = _pending(l6_space(features=["events.orders"]))
    assert _collect(staff, registration, {"method": "cash"}).status_code == 400


def test_add_guest_pay_link():
    event, staff, registration = _pending()
    response = client_for(staff).post(reverse("admin-event-registration-pay-link", kwargs={"pk": registration.pk}),
                                      {"send": False}, format="json")
    assert response.status_code == 200 and response.data["pay_link"]


def test_desk_terminal_rail_conflict_is_a_typed_409(monkeypatch):
    """Payments audit 0.12.0 R-10: a rail conflict on the terminal path used to answer 500."""
    from apps.payments.services import PaymentRailConflict

    event, staff, registration = _pending()
    monkeypatch.setattr("apps.payments.availability.online_payments_enabled", lambda *a, **k: True)

    def conflict(*args, **kwargs):
        raise PaymentRailConflict()

    monkeypatch.setattr("apps.payments.services.create_checkout_url", conflict)
    response = _collect(staff, registration, {"terminal": True})
    assert response.status_code == 409 and response.data["code"] == "payment_rail_conflict"

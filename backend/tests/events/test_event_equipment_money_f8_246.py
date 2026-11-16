"""Decision 246 (lane F8): money rules for event equipment (221b).

Planning equipment for event participants moves no stock and raises no charge, even when loans
pricing is on: a debt exists only once the kit is issued/returned through the loan workflow. The
return window changes the due date only, never an amount. Another space's ledger is never touched.
"""
from uuid import uuid4

import pytest
from django.urls import reverse

from apps.hardware_requests.models import HardwareRequest
from apps.payments.models import Payment
from tests.events.orders_helpers import l6_space, make_staff
from tests.events.test_event_equipment_desk import _enable, _event, _register
from tests.events.test_event_workshop_machines import client_for
from tests.payments.pricing.helpers import rate
from tests.return_helpers import make_product
from tests.test_request_workflow import make_user

pytestmark = pytest.mark.django_db(transaction=True)
CHARGES = {"charges.enabled", "charges.loans", "charges.pricing"}


def _plan_world(slug, *, priced=True):
    maker = l6_space(slug)
    _enable(maker, "public_inventory")
    maker.public_site_enabled = maker.public_inventory_enabled = True
    maker.enabled_features = sorted(set(maker.enabled_features or []) | (CHARGES if priced else set()))
    maker.save(update_fields=["public_site_enabled", "public_inventory_enabled", "enabled_features"])
    if priced:
        rate(maker, "loans", rental_per_day="3.00")
    staff, event = make_staff(maker), _event(maker)
    event.equipment_return_hours = 24
    event.save(update_fields=["equipment_return_hours"])
    product = make_product(maker, name="Soldering iron", total_quantity=10, available_quantity=10)
    people = [make_user(f"f8-221b-{slug}-{i}-{uuid4().hex[:5]}") for i in range(2)]
    regs = [_register(event, person) for person in people]
    url = reverse("event-equipment-plan", kwargs={"makerspace_id": maker.pk, "event_id": event.pk})
    body = {"operation_id": str(uuid4()), "requested_for": "Soldering lab",
            "lines": [{"product_id": product.pk, "quantity": 1}],
            "participants": [{"registration_id": reg.pk} for reg in regs]}
    return maker, client_for(staff), url, body, product


def _debts(maker):
    return Payment.objects.filter(makerspace=maker)


def test_planning_with_loans_pricing_on_raises_no_debt_and_moves_no_stock():
    maker, client, url, body, product = _plan_world("f8-221b-priced")
    response = client.post(url, body, format="json")
    assert response.status_code == 200, response.data
    assert [row["outcome"] for row in response.data["results"]] == ["created", "created"]
    assert HardwareRequest.objects.filter(makerspace=maker).count() == 2
    assert not _debts(maker).exists()
    product.refresh_from_db()
    assert product.available_quantity == 10


def test_a_dry_run_and_a_replay_never_create_a_debt():
    maker, client, url, body, _product = _plan_world("f8-221b-replay")
    assert client.post(url, {**body, "dry_run": True}, format="json").status_code == 200
    assert not _debts(maker).exists()
    assert client.post(url, body, format="json").status_code == 200
    assert client.post(url, body, format="json").status_code == 200  # replayed, not a second charge
    assert not _debts(maker).exists()
    assert HardwareRequest.objects.filter(makerspace=maker).count() == 2


def test_an_unpriced_space_plans_the_same_way_with_no_ledger_rows():
    maker, client, url, body, _product = _plan_world("f8-221b-free", priced=False)
    assert client.post(url, body, format="json").status_code == 200
    assert not _debts(maker).exists()


def test_another_spaces_ledger_stays_empty_when_one_space_plans_equipment():
    maker, client, url, body, _product = _plan_world("f8-221b-iso-a")
    other = _plan_world("f8-221b-iso-b")[0]
    assert client.post(url, body, format="json").status_code == 200
    assert not _debts(other).exists() and not HardwareRequest.objects.filter(makerspace=other).exists()

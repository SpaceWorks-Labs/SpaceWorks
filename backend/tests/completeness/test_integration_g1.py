"""G1 integration: dashboard payments_to_record and the real console targets in attention/search links."""
from decimal import Decimal

import pytest
from django.urls import reverse

from apps.operations.dashboard_attention import build_attention
from apps.payments.models import Payment
from tests.fixed_roles.helpers import staff_account
from tests.return_helpers import authenticated_client, make_space

pytestmark = pytest.mark.django_db

REAL_TABS = {"members", "requests", "ledger", "inventory", "needsfix", "stocktake", "machines", "repairs", "events",
             "bookings", "shop", "payments", "refunds", "incidents"}


def _space(slug):
    space = make_space(slug)
    space.enabled_modules = sorted(set(space.enabled_modules or []) | {"membership", "staff_admin", "request_workflow"})
    space.save(update_fields=["enabled_modules"])
    return space


def test_full_dashboard_carries_payments_to_record_for_record_payment_holders():
    space = _space("g1-record")
    sm = staff_account(space, "g1-sm", "space_manager")
    Payment.objects.create(member=sm, makerspace=space, subject_type="loan_late_fee", subject_id=1,
                           amount=Decimal("5.00"), currency="usd", created_by=sm)
    body = authenticated_client(sm).get(reverse("operations-dashboard", args=[space.pk])).json()
    assert body["scope_mode"] == "full"
    assert body["payments_to_record"] == 1


def test_full_dashboard_omits_payments_to_record_without_the_grant():
    space = _space("g1-norecord")
    tech = staff_account(space, "g1-tech", "technician")
    body = authenticated_client(tech).get(reverse("operations-dashboard", args=[space.pk])).json()
    assert body.get("payments_to_record", 0) == 0


def test_people_counters_name_real_members_sections_not_community():
    space = _space("g1-links")
    sm = staff_account(space, "g1-links-sm", "space_manager")
    links = [row["link"] for g in build_attention(sm, space)["areas"] for row in g["items"]]
    assert all(link["tab"] != "community" for link in links)
    assert all("view" not in link["filters"] or link["tab"] != "members" for link in links)
    members = [link for link in links if link["tab"] == "members"]
    assert members and all(link["filters"].get("section") in {"requests", "tools", "guests", "volunteering"}
                           for link in members)
    assert {link["tab"] for link in links} <= REAL_TABS


def _loan_payment(space, user, subject_type="loan_late_fee"):
    return Payment.objects.create(member=user, makerspace=space, subject_type=subject_type, subject_id=1,
                                  amount=Decimal("5.00"), currency="usd", created_by=user)


def test_area_queue_all_status_ordering_and_claims_area_filter():
    space = _space("g1-queue")
    sm = staff_account(space, "g1-q-sm", "space_manager")
    open_row = _loan_payment(space, sm)
    done = _loan_payment(space, sm)
    Payment.objects.filter(pk=done.pk).update(status="paid_offline")
    client = authenticated_client(sm)
    url = reverse("payment-area-queue", args=[space.pk])
    assert {r["id"] for r in client.get(url).json()["results"]} == {open_row.pk}
    both = client.get(url, {"status": "all", "ordering": "-created_at"}).json()["results"]
    assert [r["id"] for r in both] == [done.pk, open_row.pk]
    claims = client.get(reverse("payment-area-claims", args=[space.pk]), {"area": "machines"})
    assert claims.status_code in (200, 404)  # 404 only when billing.offline_claims is off


def test_handover_desk_owns_loan_charges_only():
    from apps.payments import area_queue
    from tests.audit_explorer_helpers import custom_role_member

    space = _space("g1-handover")
    desk = custom_role_member(space, "g1-desk", ["issue_request", "return_request", "view_inventory"])
    owned = area_queue.owned_subject_types(desk, space.pk)
    assert set(owned) == {"loan_deposit", "loan_late_fee", "loan_rental", "loan_damage", "loan_lost"}
    sm = staff_account(space, "g1-desk-sm", "space_manager")
    loan, booking = _loan_payment(space, sm), _loan_payment(space, sm, "booking")
    client = authenticated_client(desk)
    ids = {r["id"] for r in client.get(reverse("payment-area-queue", args=[space.pk])).json()["results"]}
    assert ids == {loan.pk}


def test_ledger_due_filter_validates_and_filters():
    from datetime import timedelta
    from django.utils import timezone
    from apps.hardware_requests.models import HardwareRequest
    from tests.return_helpers import make_accepted_request, make_product

    space = _space("g1-ledger")
    sm = staff_account(space, "g1-led-sm", "space_manager")
    client = authenticated_client(sm)
    url = reverse("ledger", args=[space.pk])
    assert client.get(url, {"due": "bogus"}).status_code == 400
    loan = make_accepted_request(space, make_product(space), 1)
    HardwareRequest.objects.filter(pk=loan.pk).update(status="issued", return_due_at=timezone.now() + timedelta(days=2))
    soon = client.get(url, {"due": "soon"}).json()["count"]
    today = client.get(url, {"due": "today"}).json()["count"]
    assert (today, soon) == (0, 1)

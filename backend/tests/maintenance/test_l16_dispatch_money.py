"""L16 (#98, C-4, C-5, #94, Q-T3): dispatch, consent, parts, quote, approval and payout."""

from decimal import Decimal

import pytest

from apps.maintenance.models import IssueReport, RepairPart, TechnicianDispatch
from apps.maintenance.repairs import optin, services_issues as svc
from apps.payments.models_ledger_entries import LedgerEntry
from apps.procurement.models import ToBuyItem
from tests.maintenance.l16_helpers import external, in_house, switch, world
from tests.return_helpers import authenticated_client

pytestmark = pytest.mark.django_db


def opened(w, subject_type="inventory_product", subject=None):
    return svc.open_issue(w.manager, w.space, subject_type=subject_type, subject=subject or w.product,
                          title="Broken handle")


def test_dispatch_emails_records_each_send_and_assigns_the_technicians():
    w = world("l16-disp")
    issue, contact = opened(w), external(w)
    response = authenticated_client(w.manager).post(f"/api/v1/admin/issues/{issue.pk}/dispatch",
                                                    {"contact_ids": [contact.pk], "note": "Urgent"}, format="json")
    assert response.status_code == 200, response.content
    row = TechnicianDispatch.objects.get(issue=issue)
    assert (row.channel, row.status, row.sent_by_id) == ("email", "delivered", w.manager.pk)
    assert row.provider_message_id.startswith("email:")
    assert response.json()["state"] == "assigned" and response.json()["dispatches"][0]["contact_name"] == contact.name
    assert "ravi@example.test" not in response.content.decode()


def test_chat_needs_the_opt_in_and_a_failed_send_is_recorded_not_raised():
    w = world("l16-consent")
    issue, contact = opened(w), external(w, channels=["email", "telegram"])
    client = authenticated_client(w.manager)
    refused = client.post(f"/api/v1/admin/issues/{issue.pk}/dispatch",
                          {"contact_ids": [contact.pk], "channels": ["telegram"]}, format="json")
    assert refused.status_code == 409 and refused.json()["code"] == "technician_no_consent"
    assert not TechnicianDispatch.objects.exists()
    link = optin.create_link(w.manager, contact)
    token = link["telegram_start"].split()[-1]
    assert optin.telegram_start(token, 424242) and not optin.telegram_start("nope", 1)
    contact.refresh_from_db()
    assert contact.telegram_chat_id == "424242" and contact.telegram_opted_in_at
    switch(w.space, off=())
    w.space.enabled_modules = [key for key in w.space.enabled_modules if key != "telegram"]
    w.space.save(update_fields=["enabled_modules"])
    sent = client.post(f"/api/v1/admin/issues/{issue.pk}/dispatch",
                       {"contact_ids": [contact.pk], "channels": ["telegram"]}, format="json")
    assert sent.status_code == 200
    assert TechnicianDispatch.objects.get(issue=issue, channel="telegram").status == "failed"


def test_the_web_opt_in_records_whatsapp_and_sms_consent():
    from rest_framework.test import APIClient
    w = world("l16-optin")
    contact = external(w)
    token = optin.create_link(w.manager, contact)["telegram_start"].split()[-1]
    page = APIClient().get(f"/api/v1/public/technician-opt-in/{token}")
    assert page.status_code == 200 and page.json()["technician_name"] == contact.name
    assert "phone" not in page.json() and "email" not in str(page.json()["technician_name"])
    accepted = APIClient().post(f"/api/v1/public/technician-opt-in/{token}", {"channels": ["sms"]}, format="json")
    assert accepted.status_code == 200 and accepted.json()["consent"]["sms"] is True
    assert APIClient().get("/api/v1/public/technician-opt-in/wrong").status_code == 404


def test_parts_used_leave_stock_through_availability_and_parts_needed_become_to_buy_rows():
    w = world("l16-parts")
    issue = opened(w)
    svc.assign(w.manager, issue, contact=in_house(w))
    tech = authenticated_client(w.tech)
    used = tech.post(f"/api/v1/admin/issues/{issue.pk}/parts",
                     {"kind": "used", "product_id": w.product.pk, "quantity": 2}, format="json")
    assert used.status_code == 200, used.content
    w.product.refresh_from_db()
    assert w.product.available_quantity == 3
    needed = tech.post(f"/api/v1/admin/issues/{issue.pk}/parts", {"kind": "needed", "name": "Handle", "quantity": 1},
                       format="json")
    assert needed.status_code == 200
    part = RepairPart.objects.get(issue=issue, kind="needed")
    assert ToBuyItem.objects.filter(pk=part.to_buy_item_id, kind="hardware", makerspace=w.space).exists()
    switch(w.space, off=("inventory.tobuy",))
    tech.post(f"/api/v1/admin/issues/{issue.pk}/parts", {"kind": "needed", "name": "Screw", "quantity": 4},
              format="json")
    assert RepairPart.objects.get(issue=issue, name="Screw").to_buy_item_id is None


def test_quote_approval_by_the_area_manager_then_payout_through_the_ledger_only():
    w = world("l16-money")
    issue, contact = opened(w), external(w)
    svc.assign(w.manager, issue, contact=in_house(w))
    tech = authenticated_client(w.tech)
    assert tech.post(f"/api/v1/admin/issues/{issue.pk}/quote",
                     {"amount": "450.00", "currency": "inr", "contact_id": contact.pk}, format="json").status_code == 200
    manager = authenticated_client(w.manager)
    early = manager.post(f"/api/v1/admin/issues/{issue.pk}/payout", {"amount": "450", "method": "cash"},
                         format="json")
    assert early.status_code == 409 and early.json()["code"] == "quote_not_approved"
    assert tech.post(f"/api/v1/admin/issues/{issue.pk}/approve", {"approve": True}, format="json").status_code == 403
    assert authenticated_client(w.im).post(f"/api/v1/admin/issues/{issue.pk}/approve", {"approve": True},
                                           format="json").status_code == 200
    assert tech.post(f"/api/v1/admin/issues/{issue.pk}/payout", {"amount": "450", "method": "cash"},
                     format="json").status_code == 403
    paid = manager.post(f"/api/v1/admin/issues/{issue.pk}/payout",
                        {"amount": "450.00", "method": "upi", "reference": "UPI-1"}, format="json")
    assert paid.status_code == 200, paid.content
    entry = LedgerEntry.objects.get(pk=IssueReport.objects.get(pk=issue.pk).payout_entry_id)
    assert (entry.kind, entry.domain, entry.category, entry.source_kind, entry.amount) == (
        "expense", "inventory", "repair", "repairs.payout", Decimal("450.00"))
    assert entry.counterparty == contact.name
    again = manager.post(f"/api/v1/admin/issues/{issue.pk}/payout", {"amount": "450", "method": "upi"},
                         format="json")
    assert again.status_code == 409 and LedgerEntry.objects.filter(source_kind="repairs.payout").count() == 1


def test_a_machine_payout_is_tagged_with_its_machine_type():
    w = world("l16-money-mt")
    issue = opened(w, "machine", w.machine)
    svc.assign(w.manager, issue, myself=True)
    client = authenticated_client(w.manager)
    client.post(f"/api/v1/admin/issues/{issue.pk}/quote", {"amount": "10", "currency": "usd"}, format="json")
    client.post(f"/api/v1/admin/issues/{issue.pk}/approve", {"approve": True}, format="json")
    assert client.post(f"/api/v1/admin/issues/{issue.pk}/payout", {"amount": "10", "method": "cash"},
                       format="json").status_code == 200
    entry = LedgerEntry.objects.get(source_kind="repairs.payout")
    assert (entry.domain, entry.machine_type_id) == ("machines", w.kind.pk)

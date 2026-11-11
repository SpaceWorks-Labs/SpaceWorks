"""Bills are personal/finance documents, and never cash-basis movements."""

import pytest
from django.urls import reverse

from apps.operations.reports_accounting import build_accounting_journal
from apps.operations.reports_cash_book import build_payment_cash_book
from apps.payments.documents import issue_bill
from apps.payments.document_snapshot import bill_status
from apps.payments.models import Payment
from apps.payments.reconciliation import mark_offline
from tests.billing_docs.test_r1_bills import pending
from tests.rbac_f6_helpers import custom_actor
from tests.return_helpers import authenticated_client, make_member, make_space, settlement_details

pytestmark = pytest.mark.django_db


def test_bill_adds_no_cash_or_journal_movement_and_receipt_still_does():
    space, actor, payment = pending("r1-accounting")
    before = build_payment_cash_book(space.pk).records
    bill = issue_bill(payment)
    assert build_accounting_journal(space.pk).records == []
    assert build_payment_cash_book(space.pk).records == before
    mark_offline(payment, actor, settlement_details())
    records = build_accounting_journal(space.pk).records
    assert len(records) == 2
    assert {row["kind"] for row in records} == {"receipt"}
    assert bill.number not in {row["document_number"] for row in records}


@pytest.mark.parametrize("status,expected", [("pending", "Unpaid"), ("waived", "Waived"), ("canceled", "Cancelled")])
def test_bill_status_is_live_without_any_document_update(status, expected):
    _, _, payment = pending("r1-status-" + status)
    bill = issue_bill(payment)
    Payment.objects.filter(pk=payment.pk).update(status=status)
    assert bill_status(bill) == expected
    bill.refresh_from_db()
    assert bill.kind == "bill" and bill.issuer["name"] == payment.makerspace.name


def test_bill_list_kind_filter_live_settlement_and_owner_finance_access():
    space, actor, payment = pending("r1-access")
    bill = issue_bill(payment)
    url = reverse("member-payment-documents", args=[space.pk])
    owner = authenticated_client(payment.member)
    assert owner.get(url, {"kind": "bill"}).data["results"][0]["status"] == "Unpaid"
    assert owner.get(url, {"kind": "invalid"}).status_code == 400
    mark_offline(payment, actor, settlement_details())
    receipt = payment.documents.get(kind="receipt")
    result = owner.get(url, {"kind": "bill"})
    assert result.status_code == 200 and result.data["count"] == 1
    assert result.data["results"][0]["status"] == f"Paid — see receipt {receipt.number}"
    grant_url = reverse("member-payment-document-url", args=[space.pk, bill.pk])
    assert owner.get(grant_url).status_code == 200
    other = make_member("r1-other-payer", space, membership_role="custom", role="requester")
    assert authenticated_client(other).get(grant_url).status_code == 404
    finance = custom_actor(space, ["view_finance"])
    staff_url = reverse("staff-payment-document-url", args=[space.pk, bill.pk])
    assert authenticated_client(finance).get(staff_url).status_code == 200
    inventory = custom_actor(space, ["edit_inventory"], name="r1-inventory")
    assert authenticated_client(inventory).get(staff_url).status_code == 404
    foreign = make_space("r1-doc-foreign")
    assert authenticated_client(finance).get(reverse("staff-payment-document-url", args=[foreign.pk, bill.pk])).status_code == 404


def test_settings_reject_equal_prefixes_validate_instructions_and_hide_counters():
    space, actor, _ = pending("r1-settings")
    client = authenticated_client(actor)
    path = reverse("payment-billing-settings", args=[space.pk])
    assert client.patch(path, {"number_prefix": "SAME", "bill_prefix": "SAME"}, format="json").status_code == 400
    assert client.patch(path, {"bill_prefix": "bad/path"}, format="json").status_code == 400
    assert client.patch(path, {"payment_instructions": "x" * 2001}, format="json").status_code == 400
    response = client.patch(path, {"bill_prefix": "INV-", "payment_instructions": "Pay at reception."}, format="json")
    assert response.status_code == 200 and response.data["bill_prefix"] == "INV-"
    assert "next_bill_number" not in response.data and "next_document_number" not in response.data

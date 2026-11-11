"""G23: UPI QR, "I've paid" claims and the two-person check for offline income (on and off)."""

from datetime import date

import pytest

from apps.payments.finance_scope import FinanceView
from apps.payments.models import MakerspaceBillingSettings, ManualSettlement, Payment, PaymentClaim
from apps.payments.reconciliation import mark_offline
from apps.payments.upi import upi_details
from tests.l5_local.helpers import client, dues, setup, staff, switch
from tests.return_helpers import settlement_details

pytestmark = pytest.mark.django_db


def _claim_url(space, payment):
    return f"/api/v1/member/makerspaces/{space.pk}/payments/{payment.pk}/paid-claim"


def _claim(api, space, payment, reference="UTR123456789"):
    return api.post(_claim_url(space, payment), {"reference": reference, "paid_on": date.today().isoformat()},
                    format="json")


def test_upi_qr_is_for_the_exact_amount_of_a_pending_inr_charge():
    space, _manager, payer = setup("upi-qr")
    policy = MakerspaceBillingSettings.objects.create(makerspace=space, upi_vpa="space@okbank", upi_payee_name="Lab")
    payment = dues(space, payer, "250.50")
    details = upi_details(payment, policy)
    assert details["amount"] == "250.50" and "am=250.50" in details["uri"] and details["reference"] == f"SW-{payment.pk}"
    assert upi_details(dues(space, payer, "1.00", currency="usd"), policy) is None


def test_claims_are_off_by_default_and_404():
    space, _manager, payer = setup("claim-off")
    assert _claim(client(payer), space, dues(space, payer)).status_code == 404


def test_claim_then_confirm_writes_the_receipt_once():
    space, manager, payer = setup("claim-on", "billing.offline_claims")
    payment = dues(space, payer)
    response = _claim(client(payer), space, payment)
    assert response.status_code == 201
    assert _claim(client(payer), space, payment, "UTR999999999").json()["code"] == "claim_exists"
    claim = PaymentClaim.objects.get()
    confirmed = client(manager).post(f"/api/v1/admin/makerspace/{space.pk}/paid-claims/{claim.pk}/confirm")
    assert confirmed.status_code == 200 and confirmed.json()["status"] == "confirmed"
    payment.refresh_from_db()
    receipt = ManualSettlement.objects.get(payment=payment)
    assert payment.status == Payment.Status.PAID_OFFLINE and receipt.reference == "UTR123456789"
    again = client(manager).post(f"/api/v1/admin/makerspace/{space.pk}/paid-claims/{claim.pk}/confirm")
    assert again.status_code == 409


def test_a_reference_is_claimed_once_per_space_and_reject_keeps_the_debt():
    space, manager, payer = setup("claim-reject", "billing.offline_claims")
    first, second = dues(space, payer), dues(space, payer, "5.00")
    _claim(client(payer), space, first)
    claim = PaymentClaim.objects.get()
    assert client(manager).post(f"/api/v1/admin/makerspace/{space.pk}/paid-claims/{claim.pk}/reject",
                                {"note": "Not in our account"}, format="json").status_code == 200
    first.refresh_from_db()
    assert first.status == Payment.Status.PENDING
    assert _claim(client(second.member), space, second).json()["code"] == "claim_exists"


def test_maker_checker_needs_a_second_person_and_refuses_self_confirmation():
    space, manager, payer = setup("checker", "billing.maker_checker")
    second = staff("checker", space, "space_manager")
    payment = dues(space, payer)
    mark_offline(payment, manager, settlement_details(reference="CASH-7"))
    payment.refresh_from_db()
    assert payment.status == Payment.Status.PENDING and not ManualSettlement.objects.exists()
    row = client(manager).get(f"/api/v1/admin/makerspace/{space.pk}/settlements").json()["results"][0]
    refused = client(manager).post(f"/api/v1/admin/makerspace/{space.pk}/settlements/{row['id']}/confirm")
    assert refused.status_code == 409 and refused.json()["code"] == "self_confirmation"
    assert client(second).post(f"/api/v1/admin/makerspace/{space.pk}/settlements/{row['id']}/confirm").status_code == 200
    payment.refresh_from_db()
    receipt = ManualSettlement.objects.get(payment=payment)
    assert payment.status == Payment.Status.PAID_OFFLINE and receipt.recorded_by == manager


def test_without_maker_checker_offline_settlement_is_immediate():
    space, manager, payer = setup("checker-off")
    payment = dues(space, payer)
    mark_offline(payment, manager, settlement_details(reference="CASH-8"))
    payment.refresh_from_db()
    assert payment.status == Payment.Status.PAID_OFFLINE
    switch(space, "billing.maker_checker")


def test_finance_view_scopes_machine_types():
    view = FinanceView(domains=frozenset({"machines"}), machine_types=frozenset({1}),
                       record_domains=frozenset({"machines"}))
    assert view.sees("machines", 1) and not view.sees("machines", 2) and not view.sees("inventory")
    assert view.may_record("machines", 1) and not view.may_record("machines", None)

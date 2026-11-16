"""O-B3: per-FY receipt numbers while tax is off, and the per-plan SAC code on GST charges."""
from decimal import Decimal

import pytest

from apps.makerspaces.models import MakerspaceMembership, MembershipPlan, MembershipTerm
from apps.payments.models import MakerspaceTaxSettings, Payment, PaymentDocument
from apps.payments.reconciliation import mark_offline
from apps.payments.services import create_payment
from tests.l5_local.helpers import client, dues, setup, switch
from tests.return_helpers import settlement_details

pytestmark = pytest.mark.django_db


def _settle(space, manager, payer, reference):
    payment = dues(space, payer)
    mark_offline(payment, manager, settlement_details(reference=reference))
    return PaymentDocument.objects.get(payment=payment, kind="receipt")


def test_switch_off_keeps_the_release_one_series():
    space, manager, payer = setup("fy-off")
    assert _settle(space, manager, payer, "A").number_series == ""


def test_switch_on_starts_a_gapless_fy_series_and_never_renumbers():
    space, manager, payer = setup("fy-on")
    before = _settle(space, manager, payer, "A")
    switch(space, "billing.fy_receipts")
    first, second = _settle(space, manager, payer, "B"), _settle(space, manager, payer, "C")
    before.refresh_from_db()
    assert before.number_series == "" and before.fy_start is None  # the cut-over never renumbers
    assert first.number_series == "receipt" and first.number.startswith("R") and first.number.endswith("/0001")
    assert second.number.endswith("/0002") and second.tax_breakdown is None


def test_tax_on_still_uses_the_tax_invoice_series():
    space, manager, payer = setup("fy-tax", "billing.fy_receipts", "billing.tax")
    MakerspaceTaxSettings.objects.create(makerspace=space, mode="single", tax_name="VAT", rate_bps=500)
    payment = create_payment(makerspace=space, subject_type=Payment.SubjectType.MAKERSPACE_MEMBERSHIP,
                             subject_id=MakerspaceMembership.objects.get(makerspace=space, user=payer).pk,
                             member=payer, amount=Decimal("100.00"), currency="inr", created_by=manager)
    mark_offline(payment, manager, settlement_details(reference="T"))
    assert PaymentDocument.objects.get(payment=payment, kind="receipt").number_series == "invoice"


def test_plan_sac_is_frozen_on_the_charge_and_shown_on_the_invoice_line():
    space, manager, payer = setup("plan-sac", "billing.tax", "billing.plan_sac", "membership")
    MakerspaceTaxSettings.objects.create(makerspace=space, mode="gst_india", gstin="27AAPFU0939F1ZV",
                                         state_code="27")
    plan = MembershipPlan.objects.create(makerspace=space, name="Gold", interval="yearly", amount=100,
                                         currency="inr", sac_code="999293")
    membership = MakerspaceMembership.objects.get(makerspace=space, user=payer)
    term = MembershipTerm.objects.create(membership=membership, plan=plan, starts_at="2026-01-01T00:00:00Z",
                                         ends_at="2027-01-01T00:00:00Z")
    payment = create_payment(makerspace=space, subject_type=Payment.SubjectType.MEMBERSHIP_TERM_START,
                             subject_id=term.pk, member=payer, amount=Decimal("118.00"), currency="inr",
                             created_by=manager)
    assert payment.tax_snapshot["sac_code"] == "999293"
    plan.sac_code = "999999"
    plan.save()
    mark_offline(payment, manager, settlement_details(reference="S"))
    document = PaymentDocument.objects.get(payment=payment, kind="receipt")
    assert document.tax_breakdown["sac_code"] == "999293" and document.lines[0]["sac_code"] == "999293"


def test_plan_sac_needs_the_switch_and_valid_digits():
    space, manager, _payer = setup("plan-sac-api", "membership")
    plan = MembershipPlan.objects.create(makerspace=space, name="Silver", interval="yearly", amount=10,
                                         currency="inr")
    url = f"/api/v1/admin/membership-plans/{plan.pk}"
    assert client(manager).patch(url, {"sac_code": "999293"}, format="json").status_code == 400
    switch(space, "billing.tax", "billing.plan_sac")
    assert client(manager).patch(url, {"sac_code": "12"}, format="json").status_code == 400
    assert client(manager).patch(url, {"sac_code": "999293"}, format="json").json()["sac_code"] == "999293"

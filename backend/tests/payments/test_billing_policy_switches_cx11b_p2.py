"""Document, tax, receipt, capture and checker policies alter new work; old money is retained."""
from datetime import timedelta
from decimal import Decimal

import pytest
from django.db import connection
from django.utils import timezone

from apps.makerspaces.models import MakerspaceMembership, MembershipPlan, MembershipTerm
from apps.payments.documents import issue_bill
from apps.payments.models import MakerspaceBillingSettings, MakerspaceTaxSettings, Payment, PaymentDocument, SettlementConfirmation
from apps.payments.reconciliation import mark_offline
from apps.payments.reminders import discover_payments
from apps.payments.services import create_payment
from apps.payments.tax.plan_sac import with_plan_sac
from apps.payments.tax.snapshot import freeze_for_charge
from tests.l5_local.helpers import dues, setup
from tests.modules.switch_matrix_object_helpers import retained
from tests.payments.switch_helpers_cx11b_p2 import _no_write, domain_rows, read_policy_cycle, switch
from tests.return_helpers import settlement_details

pytestmark = [pytest.mark.django_db, pytest.mark.area_payments_ledger]


def test_document_creation_is_inert_off_and_retained_bill_is_idempotent_after_restoring():
    space, actor, payer = setup("p2-bill", "billing.documents")
    payment = dues(space, payer, provider="unclaimed")
    original = switch(space, "billing.documents")
    before, rows = retained({"debt": payment}), domain_rows()
    with connection.execute_wrapper(_no_write):
        assert issue_bill(payment, actor=actor) is None
    assert retained({"debt": payment}) == before and domain_rows() == rows
    switch(space, "billing.documents", original=original)
    document = issue_bill(payment, actor=actor)
    assert (document.kind, document.amount) == ("bill", Decimal("100"))
    before = retained({"debt": payment, "bill": document})
    original = switch(space, "billing.documents")
    with connection.execute_wrapper(_no_write):
        assert issue_bill(payment, actor=actor).pk == document.pk
    switch(space, "billing.documents", original=original)
    assert issue_bill(payment, actor=actor).pk == document.pk
    assert retained({"debt": payment, "bill": document}) == before


@pytest.mark.parametrize("key", ["billing.tax", "billing.plan_sac"])
def test_tax_and_plan_sac_switches_change_new_snapshots_without_changing_retained_charge(key):
    space, actor, payer = setup("p2-tax", "billing.tax", "billing.plan_sac")
    policy = MakerspaceTaxSettings.objects.create(makerspace=space, mode="gst_india", gstin="27AAPFU0939F1ZV",
        state_code="27", sac_code="999599", rate_bps=1800, prices_include_tax=False)
    plan = MembershipPlan.objects.create(makerspace=space, name="Retained plan", interval="yearly",
        amount=100, currency="inr", sac_code="999293")
    membership = MakerspaceMembership.objects.get(makerspace=space, user=payer)
    term = MembershipTerm.objects.create(membership=membership, plan=plan, starts_at=timezone.now(),
                                         ends_at=timezone.now() + timedelta(days=365))
    payment = create_payment(makerspace=space, subject_type="membership_term_start", subject_id=term.pk,
        member=payer, amount=Decimal("100"), currency="inr", created_by=actor)
    assert payment.tax_snapshot["sac_code"] == "999293"
    figures = {"gross": "118.00", "taxable": "100.00", "tax": "18.00", "components": [
        {"code": "cgst", "label": "CGST", "rate_bps": 900, "amount": "9.00"},
        {"code": "sgst", "label": "SGST", "rate_bps": 900, "amount": "9.00"}]}
    assert (payment.amount, payment.currency) == (Decimal("118.00"), "inr")
    assert {key: payment.tax_snapshot[key] for key in ("rate_bps", "currency", "inclusive", "figures")} == {
        "rate_bps": 1800, "currency": "inr", "inclusive": False, "figures": figures}
    if key == "billing.tax":
        def read():
            amount, frozen = freeze_for_charge(space, Decimal("100"), "inr", payer)
            return amount, None if frozen is None else {
                key: frozen[key] for key in ("rate_bps", "currency", "inclusive", "entered_amount", "figures")}
        on = (Decimal("118.00"), {"rate_bps": 1800, "currency": "inr", "inclusive": False,
                                  "entered_amount": "100.00", "figures": figures})
        off = (Decimal("100.00"), None)
    else:
        read = lambda: with_plan_sac(space, "membership_term_start", term.pk, {"mode": "gst_india", "sac_code": "999599"})["sac_code"]
        on, off = "999293", "999599"
    read_policy_cycle(space, {"policy": policy, "plan": plan, "term": term, "debt": payment}, key, read, on, off)


def test_fy_receipt_switch_keeps_both_old_series_and_resumes_gapless_fy_series():
    space, actor, payer = setup("p2-fy", "billing.fy_receipts")
    # Tax is absent, and only offline settlement issues documents.
    def settle(reference):
        payment = dues(space, payer, provider="unclaimed")
        mark_offline(payment, actor, settlement_details(reference=reference))
        return PaymentDocument.objects.get(payment=payment, kind="receipt")
    first = settle("P2-FY-1")
    assert first.number_series == "receipt" and first.sequence == 1
    before = retained({"receipt": first})
    original = switch(space, "billing.fy_receipts")
    second = settle("P2-LEGACY")
    assert (second.number_series, second.fy_start) == ("", None)
    assert retained({"receipt": first}) == before
    switch(space, "billing.fy_receipts", original=original)
    third = settle("P2-FY-2")
    assert (third.number_series, third.sequence, third.fy_start) == ("receipt", 2, first.fy_start)
    assert retained({"receipt": first}) == before


def test_checker_policy_preserves_pending_proposal_off_and_applies_again_after_restoring():
    space, actor, payer = setup("p2-checker", "billing.maker_checker")
    payment = dues(space, payer, provider="unclaimed")
    mark_offline(payment, actor, settlement_details(reference="P2-PROPOSAL"))
    proposal = SettlementConfirmation.objects.get(payment=payment)
    assert Payment.objects.get(pk=payment.pk).status == "pending"
    before = retained({"debt": payment, "proposal": proposal})
    original = switch(space, "billing.maker_checker")
    second = dues(space, payer, provider="unclaimed")
    mark_offline(second, actor, settlement_details(reference="P2-IMMEDIATE"))
    assert Payment.objects.get(pk=second.pk).status == "paid_offline"
    assert retained({"debt": payment, "proposal": proposal}) == before
    switch(space, "billing.maker_checker", original=original)
    third = dues(space, payer, provider="unclaimed")
    mark_offline(third, actor, settlement_details(reference="P2-PROPOSAL-2"))
    assert Payment.objects.get(pk=third.pk).status == "pending"
    assert SettlementConfirmation.objects.filter(payment__makerspace=space).count() == 2
    assert retained({"debt": payment, "proposal": proposal}) == before


@pytest.mark.parametrize("key", ["billing.reminders", "notifications"])
def test_reminder_discovery_is_empty_off_and_restores_same_due_debt(key):
    from zoneinfo import ZoneInfo
    space, actor, payer = setup("p2-remind", "billing.reminders")
    policy, _ = MakerspaceBillingSettings.objects.update_or_create(makerspace=space, defaults={
        "reminder_days_before": [3, 1], "reminder_days_after": [2, 5], "max_reminders": 5})
    payment = dues(space, payer, provider="unclaimed", due_at=timezone.now())
    now = timezone.now()
    def read():
        return [(item.subject, item.kind) for item in discover_payments(space, now, 50, ZoneInfo(space.timezone))]
    expected = [(str(payment.pk), kind) for kind in ("day:-3", "day:-1", "day:0", "day:2", "day:5")]
    read_policy_cycle(space, {"debt": payment, "policy": policy}, key, read, expected, [])

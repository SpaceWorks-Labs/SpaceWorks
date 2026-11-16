"""Open items batch 5 (payments audit 0.12.0): A1/A2 audit dedupe, A3 supersede, A4 Razorpay
idempotency header, A8 translated claim conflicts, A12 venue fee retry, A13 shop Idempotency-Key."""

import ast
from datetime import timedelta
from pathlib import Path
from unittest import mock

import pytest
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.payments.models import Payment, PaymentClaim, SettlementConfirmation
from apps.payments.offline_claims import submit_claim
from apps.payments.online_settlement import settle_capture
from apps.payments.providers.base import RefundRequest
from apps.payments.providers.razorpay import RazorpayProvider
from apps.payments.terminal_settlement import (
    handle_razorpay_paid_after_terminal, handle_stripe_paid_after_terminal,
)
from tests.l5_local.helpers import dues, setup

pytestmark = pytest.mark.django_db
PAYMENTS = Path(__file__).parents[2] / "apps" / "payments"


def _count(payment, action):
    return AuditLog.objects.filter(action=action, target_id=str(payment.pk)).count()


def _offline(slug):
    space, _manager, payer = setup(slug)
    payment = dues(space, payer, "10.00")
    Payment.objects.filter(pk=payment.pk).update(status=Payment.Status.PAID_OFFLINE)
    payment.refresh_from_db()
    return payment


def test_a_stripe_capture_repeated_by_several_events_is_flagged_once():
    payment = _offline("b5-stripe-dedupe")
    for event_id in ("evt_1", "evt_2", "evt_3"):
        handle_stripe_paid_after_terminal(payment, event_id=event_id, intent_id="pi_late")
    assert _count(payment, "payment.paid_after_terminal") == 1
    assert _count(payment, "payment.double_paid_refund_required") == 1
    first = AuditLog.objects.get(action="payment.paid_after_terminal", target_id=str(payment.pk))
    assert first.meta["prior_status"] == "paid_offline" and first.meta["provider_payment_id"] == "pi_late"


def test_a_different_stripe_capture_is_a_new_fact():
    payment = _offline("b5-stripe-two")
    handle_stripe_paid_after_terminal(payment, event_id="evt_a", intent_id="pi_a")
    handle_stripe_paid_after_terminal(payment, event_id="evt_b", intent_id="pi_b")
    assert _count(payment, "payment.double_paid_refund_required") == 2


def test_a_repeat_of_the_capture_that_settled_online_is_not_after_terminal():
    space, _manager, payer = setup("b5-ordinary-dup")
    payment = dues(space, payer, "10.00")
    settle_capture(payment, provider=Payment.Provider.STRIPE, capture_id="pi_ok", event_id="evt_ok",
                   minor=1000, currency="inr")
    payment.refresh_from_db()
    handle_stripe_paid_after_terminal(payment, event_id="evt_dup", intent_id="pi_ok")
    assert _count(payment, "payment.paid_after_terminal") == 0


def test_a_late_capture_on_a_waived_charge_records_the_original_prior_status_once():
    space, _manager, payer = setup("b5-waived-late")
    payment = dues(space, payer, "10.00")
    Payment.objects.filter(pk=payment.pk).update(status=Payment.Status.WAIVED)
    payment.refresh_from_db()
    handle_stripe_paid_after_terminal(payment, event_id="evt_1", intent_id="pi_w")
    payment.refresh_from_db()
    handle_stripe_paid_after_terminal(payment, event_id="evt_2", intent_id="pi_w")
    rows = AuditLog.objects.filter(action="payment.paid_after_terminal", target_id=str(payment.pk))
    assert rows.count() == 1 and rows.get().meta["prior_status"] == "waived"


def test_razorpay_duplicate_events_of_the_same_capture_write_one_audit_row():
    payment = _offline("b5-razorpay-dedupe")
    for event_id in ("evt_1", "evt_2"):
        handle_razorpay_paid_after_terminal(payment, event_id=event_id, payment_id="pay_late")
    assert _count(payment, "payment.paid_after_terminal") == 1
    assert _count(payment, "payment.double_paid_refund_required") == 1


def _claim(slug):
    space, manager, payer = setup(slug)
    payment = dues(space, payer, "10.00")
    claim = submit_claim(payment, claimant=payer, reference="UTR123456", paid_on=timezone.localdate())
    return space, manager, payment, claim


def test_an_online_capture_closes_the_open_claim():
    _space, _manager, payment, claim = _claim("b5-supersede-online")
    settle_capture(payment, provider=Payment.Provider.STRIPE, capture_id="pi_s", event_id="evt_s",
                   minor=1000, currency="inr")
    claim.refresh_from_db()
    assert claim.status == PaymentClaim.Status.REJECTED and claim.decided_at is not None
    assert _count(payment, "payment.paid_claim_superseded") == 1


def test_confirming_a_claim_does_not_supersede_itself():
    from apps.payments.offline_claims import confirm_claim

    space, manager, payment, claim = _claim("b5-supersede-self")
    confirm_claim(actor=manager, makerspace_id=space.pk, claim_id=claim.pk)
    claim.refresh_from_db()
    assert claim.status == PaymentClaim.Status.CONFIRMED
    assert _count(payment, "payment.paid_claim_superseded") == 0


def test_an_awaiting_proposal_is_closed_when_the_charge_settles_another_way():
    space, manager, payer = setup("b5-supersede-proposal")
    payment = dues(space, payer, "10.00")
    row = SettlementConfirmation.objects.create(
        payment=payment, method="cash", received_at=timezone.now(), amount=payment.amount,
        currency=payment.currency, proposed_by=manager)
    settle_capture(payment, provider=Payment.Provider.STRIPE, capture_id="pi_p", event_id="evt_p",
                   minor=1000, currency="inr")
    row.refresh_from_db()
    assert row.status == SettlementConfirmation.Status.REJECTED
    assert _count(payment, "payment.settlement_superseded") == 1


def test_razorpay_refund_posts_an_idempotency_key():
    seen = {}

    def fake_request(self, source, method, path, body=None, *, idempotency_key=None):
        seen.update(path=path, key=idempotency_key)
        return {"id": "rfnd_1", "status": "processed"}

    request = RefundRequest(payment_id="pay_1", amount_minor=1000, currency="inr", reference="42",
                            idempotency_key="payment-refund-42", metadata={}, refund_application_fee=False)
    with mock.patch.object(RazorpayProvider, "_request", fake_request):
        RazorpayProvider().create_refund(mock.Mock(), request)
    assert seen == {"path": "/payments/pay_1/refund", "key": "payment-refund-42"}


def test_every_claim_conflict_message_is_translatable():
    tree = ast.parse((PAYMENTS / "offline_claims.py").read_text(encoding="utf8"))
    calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)
             and getattr(node.func, "id", "") == "ClaimConflict"]
    assert calls
    for node in calls:
        first = node.args[0]
        assert isinstance(first, ast.Call) and first.func.id == "gettext", ast.unparse(node)


def test_a_failed_venue_fee_is_charged_again_by_the_retry_pass():
    from apps.events.models import Event, EventVenueFee
    from apps.events.venue_fee_retry import retry_unraised_venue_fees
    from tests.events.orders_helpers import l6_space, make_staff, verified

    space = l6_space()
    make_staff(space)
    payer = verified("retry-organiser")
    starts = timezone.now() + timedelta(days=2)
    event = Event.objects.create(makerspace=space, title="Retry meetup", starts_at=starts,
                                 ends_at=starts + timedelta(hours=2), status="published")
    fee = EventVenueFee.objects.create(makerspace=space, event=event, payer=payer, mode="custom", basis="flat",
                                       amount="20.00")
    EventVenueFee.objects.filter(pk=fee.pk).update(updated_at=timezone.now() - timedelta(minutes=30))
    with mock.patch("apps.events.venue_fees.charge") as charge:
        counts = retry_unraised_venue_fees()
    charge.assert_called_once()
    assert counts["charged"] == 1

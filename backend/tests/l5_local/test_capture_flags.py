"""G24 capture flags, G25 disputes and G26 method labels: record, flag, hold -- never refund."""

import pytest

from apps.payments.models import Payment, PaymentCaptureFlag, PaymentDispute, PaymentDocument, Refund
from apps.payments.services_webhooks import apply_webhook_event
from tests.l5_local.helpers import client, dues, setup, switch

pytestmark = pytest.mark.django_db


def _online(slug, amount="100.00", *features):
    space, manager, payer = setup(slug, *features)
    payment = dues(space, payer, amount, provider=Payment.Provider.STRIPE)
    Payment.objects.filter(pk=payment.pk).update(stripe_checkout_session_id=f"cs_{slug}")
    return space, manager, payment


def _paid(space, slug, event_id, amount_minor, currency="inr", card=True):
    obj = {"id": f"cs_{slug}", "payment_status": "paid", "payment_intent": f"pi_{slug}",
           "amount_total": amount_minor, "currency": currency}
    return apply_webhook_event(space, {"id": event_id, "type": "checkout.session.completed",
                                       "data": {"object": obj}})


def test_a_mismatched_capture_is_accepted_flagged_and_its_receipt_held():
    space, manager, payment = _online("flag-mismatch", "100.00", "billing.capture_flags")
    result = _paid(space, "flag-mismatch", "evt_mm", 9000)
    assert result.status == Payment.Status.PAID_ONLINE
    flag = PaymentCaptureFlag.objects.get(payment=payment)
    assert flag.kind == "mismatch" and str(flag.captured_amount) == "90.00"
    assert not PaymentDocument.objects.filter(payment=payment, kind="receipt").exists()
    resolved = client(manager).post(f"/api/v1/admin/makerspace/{space.pk}/capture-flags/{flag.pk}/resolve",
                                    {"resolution": "issue_received"}, format="json")
    assert resolved.status_code == 200
    assert PaymentDocument.objects.get(payment=payment, kind="receipt").amount == flag.captured_amount
    assert not Refund.objects.exists()


def test_without_the_switch_a_mismatch_keeps_release_one_behaviour():
    space, _manager, payment = _online("flag-off", "100.00")
    switch(space, "billing.capture_flags", on=False)
    _paid(space, "flag-off", "evt_off", 9000)
    assert not PaymentCaptureFlag.objects.exists()
    assert PaymentDocument.objects.filter(payment=payment, kind="receipt").exists()


def test_money_for_a_cancelled_charge_is_recorded_and_a_refund_case_needs_staff():
    space, manager, payment = _online("flag-late", "100.00", "billing.capture_flags")
    Payment.objects.filter(pk=payment.pk).update(status=Payment.Status.CANCELED)
    _paid(space, "flag-late", "evt_late", 10000)
    payment.refresh_from_db()
    flag = PaymentCaptureFlag.objects.get(payment=payment)
    assert payment.status == Payment.Status.PAID_ONLINE and flag.kind == "late"
    response = client(manager).post(f"/api/v1/admin/makerspace/{space.pk}/capture-flags/{flag.pk}/resolve",
                                    {"resolution": "refund_case"}, format="json")
    assert response.status_code == 200
    assert payment.refund_cases.count() == 1
    assert not Refund.objects.exists()


def test_dispute_is_recorded_never_cancels_or_refunds():
    space, manager, payment = _online("dispute", "100.00", "billing.capture_flags")
    _paid(space, "dispute", "evt_paid", 10000)
    dispute_event = {"id": "evt_dp1", "type": "charge.dispute.created", "data": {"object": {
        "id": "dp_1", "payment_intent": "pi_dispute", "status": "needs_response", "amount": 10000,
        "currency": "inr", "reason": "fraudulent"}}}
    apply_webhook_event(space, dispute_event)
    apply_webhook_event(space, dispute_event)
    apply_webhook_event(space, {"id": "evt_dp2", "type": "charge.dispute.closed", "data": {"object": {
        "id": "dp_1", "payment_intent": "pi_dispute", "status": "lost", "amount": 10000, "currency": "inr"}}})
    dispute = PaymentDispute.objects.get()
    payment.refresh_from_db()
    assert dispute.status == "lost" and dispute.events.count() == 2
    assert payment.status == Payment.Status.PAID_ONLINE and not Refund.objects.exists()
    url = f"/api/v1/admin/makerspace/{space.pk}/disputes"
    assert client(manager).get(url).json()["count"] == 1
    switch(space, "billing.disputes", on=False)
    assert client(manager).get(url).status_code == 404
    assert PaymentDispute.objects.count() == 1


def test_card_label_fills_once_from_the_provider():
    space, _manager, payment = _online("label")
    apply_webhook_event(space, {"id": "evt_ch", "type": "charge.succeeded", "data": {"object": {
        "id": "ch_1", "payment_intent": "pi_label",
        "payment_method_details": {"type": "card", "card": {"brand": "visa", "last4": "4242"}}}}})
    payment.refresh_from_db()
    assert payment.method_label == ""  # no capture recorded for pi_label yet
    Payment.objects.filter(pk=payment.pk).update(stripe_payment_intent_id="pi_label")
    apply_webhook_event(space, {"id": "evt_ch2", "type": "charge.succeeded", "data": {"object": {
        "id": "ch_2", "payment_intent": "pi_label",
        "payment_method_details": {"type": "card", "card": {"brand": "visa", "last4": "4242"}}}}})
    payment.refresh_from_db()
    assert payment.method_label == "Visa ••4242"

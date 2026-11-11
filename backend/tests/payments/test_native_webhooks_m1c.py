"""Phase 1c: signed native captures preserve anchors and immutable settled ledgers."""

import json
from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.payments.models import Payment, PaymentDocument, ProcessedStripeEvent, Refund
from apps.payments.reconciliation import mark_offline, waive
from tests.payments.test_mobile_razorpay_settlement import native_payment
from tests.payments.test_razorpay_provider import sign
from tests.return_helpers import make_member, settlement_details

pytestmark = pytest.mark.django_db


def deliver(client, payment, event_type, event_id, *, capture_id="pay_m1c"):
    payload = {"payment": {"entity": {
        "id": capture_id, "order_id": payment.external_order_id,
        "amount": 1250, "currency": "INR", "status": "captured",
    }}}
    if event_type == "order.paid":
        payload["order"] = {"entity": {
            "id": payment.external_order_id, "amount": 1250,
            "currency": "INR", "status": "paid",
        }}
    body = json.dumps({"event": event_type, "payload": payload}).encode()
    response = client.post(
        reverse("razorpay-webhook", args=[payment.makerspace.public_code]),
        data=body, content_type="application/json",
        HTTP_X_RAZORPAY_SIGNATURE=sign(body), HTTP_X_RAZORPAY_EVENT_ID=event_id,
    )
    assert response.status_code == 200
    return response


def audits(payment, action=None):
    rows = AuditLog.objects.filter(
        makerspace=payment.makerspace, target_type="payments.payment",
        target_id=str(payment.pk),
    )
    return rows.filter(action=action) if action else rows


def events(payment):
    return ProcessedStripeEvent.objects.filter(
        makerspace=payment.makerspace, provider=Payment.Provider.RAZORPAY,
    )


def payment_snapshot(payment):
    return Payment.objects.filter(pk=payment.pk).values().get()


def test_order_paid_settles_native_order_and_duplicate_delivery_is_noop(client):
    space, member, payment = native_payment("m1c-webhook-paid")

    deliver(client, payment, "order.paid", "evt_m1c_order")

    payment.refresh_from_db()
    assert payment.status == Payment.Status.PAID_ONLINE
    assert payment.external_payment_id == "pay_m1c"
    assert payment.external_order_id == "order_settlement"
    assert payment.online_rail == Payment.OnlineRail.NATIVE_PAYMENT_INTENT
    settled = audits(payment, "payment.paid_online").get()
    assert settled.meta == {"provider": "razorpay", "event_id": "evt_m1c_order"}
    before = payment_snapshot(payment)
    audit_ids = set(audits(payment).values_list("pk", flat=True))
    document_ids = set(PaymentDocument.objects.filter(payment=payment).values_list("pk", flat=True))

    deliver(client, payment, "order.paid", "evt_m1c_order")

    assert payment_snapshot(payment) == before
    assert set(audits(payment).values_list("pk", flat=True)) == audit_ids
    assert set(PaymentDocument.objects.filter(payment=payment).values_list("pk", flat=True)) == document_ids
    assert list(events(payment).values_list("stripe_event_id", flat=True)) == ["evt_m1c_order"]
    assert not audits(payment, "payment.double_paid_refund_required").exists()


@pytest.mark.parametrize("event_type", ["order.paid", "payment.captured"])
def test_waived_native_order_late_capture_restores_paid_status_and_refund_anchor(client, event_type):
    space, member, payment = native_payment("m1c-webhook-waived")
    staff = make_member("m1c-webhook-waived-staff", space)
    waive(payment, staff)
    payment.refresh_from_db()
    assert payment.status == Payment.Status.WAIVED
    assert payment.external_payment_id is None

    deliver(client, payment, event_type, "evt_m1c_waived")

    payment.refresh_from_db()
    assert payment.status == Payment.Status.PAID_ONLINE
    assert payment.external_payment_id == "pay_m1c"
    assert payment.external_order_id == "order_settlement"
    assert payment.amount == Decimal("12.50")
    assert payment.currency == "inr"
    meta = audits(payment, "payment.paid_after_terminal").get().meta
    assert meta["prior_status"] == Payment.Status.WAIVED
    assert meta["resolved_status"] == Payment.Status.PAID_ONLINE
    assert not audits(payment, "payment.double_paid_refund_required").exists()


@pytest.mark.parametrize("first_type,second_type", [
    ("order.paid", "payment.captured"), ("payment.captured", "order.paid"),
])
def test_distinct_event_ids_for_same_capture_on_paid_row_never_flag_excess(client, first_type, second_type):
    space, member, payment = native_payment("m1c-webhook-same-capture")
    deliver(client, payment, first_type, "evt_m1c_first")
    payment.refresh_from_db()
    assert payment.external_payment_id == "pay_m1c"
    before = payment_snapshot(payment)

    deliver(client, payment, second_type, "evt_m1c_second")

    assert payment_snapshot(payment) == before
    assert set(events(payment).values_list("stripe_event_id", flat=True)) == {
        "evt_m1c_first", "evt_m1c_second",
    }
    assert audits(payment, "payment.paid_online").count() == 1
    assert not audits(payment, "payment.double_paid_refund_required").exists()


def test_offline_late_capture_audits_provider_id_without_touching_payment_or_refunds(client):
    space, member, payment = native_payment("m1c-webhook-offline")
    staff = make_member("m1c-webhook-offline-staff", space)
    mark_offline(payment, staff, settlement_details())
    payment.refresh_from_db()
    now = timezone.now()
    Refund.objects.create(
        payment=payment, amount=Decimal("2.00"), currency="inr", created_by=staff,
        provider=Refund.Provider.MANUAL, status=Refund.Status.SUCCEEDED,
        method="cash", refunded_at=now, settled_at=now,
    )
    before = payment_snapshot(payment)
    refunds_before = list(Refund.objects.filter(payment=payment).values())
    total_before = Refund.counted_total(payment)
    assert total_before == Decimal("2.00")

    deliver(client, payment, "order.paid", "evt_m1c_offline_order", capture_id="pay_excess")

    condition = audits(payment, "payment.double_paid_refund_required").get()
    assert condition.meta == {
        "provider": "razorpay", "event_id": "evt_m1c_offline_order",
        "prior_status": Payment.Status.PAID_OFFLINE,
        "provider_payment_id": "pay_excess", "amount_minor": 1250, "currency": "INR",
    }
    # One capture has two webhook shapes, plus a duplicate delivery of the second.
    deliver(client, payment, "payment.captured", "evt_m1c_offline_capture", capture_id="pay_excess")
    deliver(client, payment, "payment.captured", "evt_m1c_offline_capture", capture_id="pay_excess")

    assert audits(payment, "payment.double_paid_refund_required").count() == 1
    assert payment_snapshot(payment) == before
    assert list(Refund.objects.filter(payment=payment).values()) == refunds_before
    assert Refund.counted_total(payment) == total_before

    # A genuinely different capture gets its own condition, exactly once.
    deliver(client, payment, "order.paid", "evt_m1c_second_order", capture_id="pay_second")
    deliver(client, payment, "payment.captured", "evt_m1c_second_capture", capture_id="pay_second")
    deliver(client, payment, "payment.captured", "evt_m1c_second_retry", capture_id="pay_second")

    conditions = audits(payment, "payment.double_paid_refund_required")
    assert conditions.count() == 2
    assert conditions.filter(meta__provider_payment_id="pay_excess").count() == 1
    assert conditions.filter(meta__provider_payment_id="pay_second").count() == 1
    assert payment_snapshot(payment) == before
    assert list(Refund.objects.filter(payment=payment).values()) == refunds_before
    assert Refund.counted_total(payment) == total_before

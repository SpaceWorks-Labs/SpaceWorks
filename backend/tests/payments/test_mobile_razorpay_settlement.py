"""Native captures retain refund anchors and flag each excess collection once."""

import json
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.payments.models import Payment, Refund
from apps.payments.providers import get_provider
from apps.payments.reconciliation_rail import _expire_checkout_best_effort
from apps.payments.resolution import source_for_payment
from apps.payments.services_webhooks import apply_razorpay_webhook_event
from tests.payments.test_mobile_intent_vendor import _razorpay_debt
from tests.payments.test_razorpay_provider import sign

pytestmark = pytest.mark.django_db


def native_payment(slug):
    space, member, payment = _razorpay_debt(slug, claimed=True)
    payment.online_rail = Payment.OnlineRail.NATIVE_PAYMENT_INTENT
    payment.external_order_id = 'order_settlement'
    payment.save()
    return space, member, payment


def capture(payment, event_type, event_id, *, payment_id='pay_capture'):
    body = json.dumps({
        'event': event_type,
        'payload': {
            'order': {'entity': {'id': payment.external_order_id, 'amount': 1250, 'currency': 'INR'}},
            'payment': {'entity': {
                'id': payment_id, 'order_id': payment.external_order_id,
                'amount': 1250, 'currency': 'INR',
            }},
        },
    }).encode()
    event = get_provider('razorpay').verify_webhook(
        source_for_payment(payment), payload=body,
        headers={'X-Razorpay-Signature': sign(body), 'X-Razorpay-Event-Id': event_id},
    )
    return apply_razorpay_webhook_event(payment.makerspace, event)


def excess(payment):
    return AuditLog.objects.filter(
        target_type='payments.payment', target_id=str(payment.pk),
        action='payment.double_paid_refund_required',
    )


@pytest.mark.parametrize('initial_status', [Payment.Status.PENDING, Payment.Status.WAIVED])
def test_order_paid_and_capture_store_anchor_without_false_excess(initial_status):
    space, member, payment = native_payment('rzp-anchor')
    if initial_status == Payment.Status.WAIVED:
        Payment.objects.filter(pk=payment.pk).update(status=initial_status)

    capture(payment, 'order.paid', 'evt_order')
    payment.refresh_from_db()
    assert payment.status == Payment.Status.PAID_ONLINE
    assert payment.external_payment_id == 'pay_capture'
    before = Payment.objects.filter(pk=payment.pk).values().get()
    capture(payment, 'order.paid', 'evt_order')
    capture(payment, 'payment.captured', 'evt_capture')

    assert Payment.objects.filter(pk=payment.pk).values().get() == before
    assert not excess(payment).exists()
    assert AuditLog.objects.filter(action='payment.paid_online', target_id=str(payment.pk)).count() == (initial_status == Payment.Status.PENDING)


@pytest.mark.parametrize('initial_status', [Payment.Status.PAID_OFFLINE, Payment.Status.PAID_ONLINE])
def test_excess_is_once_per_capture_with_no_payment_or_refund_changes(initial_status):
    space, member, payment = native_payment('rzp-excess')
    if initial_status == Payment.Status.PAID_ONLINE:
        capture(payment, 'order.paid', 'evt_original', payment_id='pay_original')
    else:
        Payment.objects.filter(pk=payment.pk).update(status=initial_status)
    payment.refresh_from_db()
    refund_fields = {'provider': Refund.Provider.RAZORPAY, 'status': Refund.Status.PENDING}
    if initial_status == Payment.Status.PAID_OFFLINE:
        refund_fields = {
            'provider': Refund.Provider.MANUAL, 'status': Refund.Status.SUCCEEDED,
            'method': 'cash', 'refunded_at': timezone.now(), 'settled_at': timezone.now(),
        }
    Refund.objects.create(
        payment=payment, amount=Decimal('2.00'), currency='inr', created_by=member,
        **refund_fields,
    )
    before = Payment.objects.filter(pk=payment.pk).values().get()
    refunds_before = list(Refund.objects.filter(payment=payment).values())
    total_before = Refund.counted_total(payment)

    capture(payment, 'order.paid', 'evt_excess_order', payment_id='pay_excess')
    capture(payment, 'payment.captured', 'evt_excess_capture', payment_id='pay_excess')
    capture(payment, 'payment.captured', 'evt_excess_capture', payment_id='pay_excess')

    assert excess(payment).count() == 1
    meta = excess(payment).get().meta
    assert meta['provider_payment_id'] == 'pay_excess'
    assert meta['amount_minor'] == 1250
    assert meta['currency'] == 'INR'
    assert Payment.objects.filter(pk=payment.pk).values().get() == before
    assert list(Refund.objects.filter(payment=payment).values()) == refunds_before
    assert Refund.counted_total(payment) == total_before

    capture(payment, 'payment.captured', 'evt_second_excess', payment_id='pay_second_excess')
    assert excess(payment).count() == 2


def test_native_order_closes_locally_without_link_cancel(monkeypatch):
    space, member, payment = native_payment('rzp-close-order')
    def unexpected(*args, **kwargs):
        pytest.fail('Razorpay Orders have no cancel API')
    monkeypatch.setattr('apps.payments.reconciliation_rail.source_for_payment', unexpected)

    _expire_checkout_best_effort(payment)

    assert payment.stripe_checkout_session_expired_at is not None
    assert payment.external_order_id == 'order_settlement'


def test_hosted_razorpay_link_still_uses_link_cancel(monkeypatch):
    space, member, payment = _razorpay_debt('rzp-close-link', claimed=True)
    payment.online_rail = Payment.OnlineRail.CHECKOUT
    payment.external_order_id = 'plink_close'
    calls = []
    monkeypatch.setattr(
        'apps.payments.providers.razorpay.RazorpayProvider._request',
        lambda self, source, method, path, body=None: calls.append((method, path)) or {},
    )
    _expire_checkout_best_effort(payment)
    assert calls == [('POST', '/payment_links/plink_close/cancel')]
    assert payment.stripe_checkout_session_expired_at is not None

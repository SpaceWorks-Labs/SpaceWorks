"""Recovery and native/hosted rail exclusion, without real provider I/O."""

from decimal import Decimal

import pytest

from apps.audit.models import AuditLog
from apps.payments import services_mobile_razorpay
from apps.payments.models import Payment
from apps.payments.providers import PaymentsUnavailable
from apps.payments.providers.razorpay import RazorpayProvider, RazorpayRequestError
from apps.payments.services_mobile import create_mobile_intent
from tests.payments.test_mobile_intent_vendor import _razorpay_debt
from tests.payments.test_mobile_payments import device_client
from tests.payments.account_helpers import make_payer

pytestmark = pytest.mark.django_db


def order_for(payment, **changes):
    return {
        'id': 'order_mobile', 'receipt': f'sw-pay-{payment.pk}',
        'amount': 1250, 'currency': 'INR', 'status': 'created',
        'notes': {'payment_id': str(payment.pk), 'makerspace_id': str(payment.makerspace_id)},
        **changes,
    }


def test_create_once_then_fetch_stored_order(monkeypatch):
    space, member, payment = _razorpay_debt('rzp-once', claimed=True)
    calls = []
    def request(self, source, method, path, body=None):
        calls.append((method, path, body))
        if path.startswith('/orders?'):
            return {'items': []}
        if method == 'POST':
            assert body == {key: order_for(payment)[key] for key in ('receipt', 'amount', 'currency', 'notes')}
            assert len(body['receipt']) <= 40
        return order_for(payment)
    monkeypatch.setattr(RazorpayProvider, '_request', request)

    first = create_mobile_intent(payment.pk, actor=member)
    second = create_mobile_intent(payment.pk, actor=member)

    assert first == second
    assert [(method, path.split('?')[0]) for method, path, _ in calls] == [
        ('GET', '/orders'), ('POST', '/orders'), ('GET', '/orders/order_mobile'),
    ]
    assert AuditLog.objects.filter(action='payment.mobile_order_created', target_id=str(payment.pk)).count() == 1
    assert 'secret' not in str(first)


def test_lost_local_write_recovers_by_receipt(monkeypatch):
    space, member, payment = _razorpay_debt('rzp-lost', claimed=False)
    remote, creates = [], []
    def request(self, source, method, path, body=None):
        if method == 'GET':
            return {'items': remote}
        creates.append(body)
        remote.append(order_for(payment))
        return remote[0]
    monkeypatch.setattr(RazorpayProvider, '_request', request)
    original = services_mobile_razorpay.audit.record
    def failed_local_write(*args, **kwargs):
        raise RuntimeError('local write lost')
    monkeypatch.setattr(services_mobile_razorpay.audit, 'record', failed_local_write)
    with pytest.raises(RuntimeError):
        create_mobile_intent(payment.pk, actor=member)
    payment.refresh_from_db()
    assert payment.external_order_id is None
    assert payment.provider == Payment.Provider.UNCLAIMED
    monkeypatch.setattr(services_mobile_razorpay.audit, 'record', original)

    result = create_mobile_intent(payment.pk, actor=member)

    assert result['order_id'] == 'order_mobile'
    assert len(creates) == 1


def test_duplicate_receipt_400_runs_lookup_again(monkeypatch):
    space, member, payment = _razorpay_debt('rzp-duplicate', claimed=True)
    methods = []
    def request(self, source, method, path, body=None):
        methods.append(method)
        if method == 'POST':
            raise RazorpayRequestError(400, 'BAD_REQUEST_ERROR', 'Receipt must be unique')
        return {'items': [] if len(methods) == 1 else [order_for(payment, status='attempted')]}
    monkeypatch.setattr(RazorpayProvider, '_request', request)

    assert create_mobile_intent(payment.pk, actor=member)['order_id'] == 'order_mobile'
    assert methods == ['GET', 'POST', 'GET']


@pytest.mark.parametrize('changes', [
    {'receipt': 'prefix-sw-pay-1'}, {'amount': 1251}, {'currency': 'USD'},
    {'notes': {'payment_id': 'wrong'}}, {'status': 'paid'}, {'id': ''},
])
def test_incompatible_lookup_is_503_without_creation(monkeypatch, changes):
    space, member, payment = _razorpay_debt('rzp-mismatch', claimed=True)
    def request(self, source, method, path, body=None):
        assert method == 'GET'
        return {'items': [order_for(payment, **changes)]}
    monkeypatch.setattr(RazorpayProvider, '_request', request)
    response = device_client(member, space).post(
        f'/api/v1/member/makerspaces/{space.pk}/payments/{payment.pk}/mobile-intent', format='json',
    )
    assert response.status_code == 503
    assert response.data['code'] == 'payments_unavailable'
    payment.refresh_from_db()
    assert payment.external_order_id is None
    assert payment.online_rail is None


def test_existing_link_returns_409_before_provider_io(monkeypatch):
    space, member, payment = _razorpay_debt('rzp-link', claimed=True)
    payment.online_rail = Payment.OnlineRail.CHECKOUT
    payment.external_order_id = 'plink_existing'
    payment.save()
    def unexpected(*args, **kwargs):
        pytest.fail('A hosted link must not reach the native provider')
    monkeypatch.setattr(RazorpayProvider, '_request', unexpected)
    response = device_client(member, space).post(
        f'/api/v1/member/makerspaces/{space.pk}/payments/{payment.pk}/mobile-intent', format='json',
    )
    assert response.status_code == 409
    assert response.data['code'] == 'payment_rail_conflict'


def test_stored_order_mismatch_is_not_replaced(monkeypatch):
    space, member, payment = _razorpay_debt('rzp-stored', claimed=True)
    payment.external_order_id = 'order_stored'
    payment.online_rail = Payment.OnlineRail.NATIVE_PAYMENT_INTENT
    payment.save()
    monkeypatch.setattr(RazorpayProvider, 'fetch_order', lambda *args: order_for(payment))
    with pytest.raises(PaymentsUnavailable):
        create_mobile_intent(payment.pk, actor=member)


def test_exact_receipt_is_selected_among_partial_matches(monkeypatch):
    space, member, payment = _razorpay_debt('rzp-exact', claimed=True)
    orders = [order_for(payment, receipt=f'sw-pay-{payment.pk}0'), order_for(payment)]
    monkeypatch.setattr(RazorpayProvider, 'fetch_orders_by_receipt', lambda *args: orders)
    assert create_mobile_intent(payment.pk, actor=member)['order_id'] == 'order_mobile'


@pytest.mark.parametrize('currency,expected', [('jpy', 13), ('kwd', 12500)])
def test_order_amount_uses_currency_minor_units(monkeypatch, currency, expected):
    space, member, payment = _razorpay_debt('rzp-exponents', claimed=True)
    payment.currency = currency
    # Decision 260: an amount finer than the provider can capture is refused, never rounded (12.50 JPY).
    payment.amount = Decimal('13') if currency == 'jpy' else Decimal('12.500')
    payment.save()
    def request(self, source, method, path, body=None, idempotency_key=None):
        if method == 'GET':
            return {'items': []}
        assert body['amount'] == expected
        return {'id': 'order_mobile', 'status': 'created', **body}
    monkeypatch.setattr(RazorpayProvider, '_request', request)
    assert create_mobile_intent(payment.pk, actor=member)['amount_minor'] == expected


def test_endpoint_preserves_online_gate_and_owner_scope(monkeypatch):
    space, member, payment = _razorpay_debt('rzp-gates', claimed=True)
    stranger = make_payer('rzp-gates-stranger', space)
    def unexpected(*args, **kwargs):
        pytest.fail('Rejected requests must not reach Razorpay')
    monkeypatch.setattr(RazorpayProvider, '_request', unexpected)
    url = f'/api/v1/member/makerspaces/{space.pk}/payments/{payment.pk}/mobile-intent'
    assert device_client(stranger, space).post(url, format='json').status_code == 404
    monkeypatch.setattr('apps.payments_rail.views_member_mobile.online_payments_enabled_for', lambda payment: False)
    response = device_client(member, space).post(url, format='json')
    assert response.status_code == 503
    assert response.data['code'] == 'payments_unavailable'


def test_endpoint_returns_native_checkout_contract(monkeypatch):
    space, member, payment = _razorpay_debt('rzp-contract', claimed=True)
    monkeypatch.setattr(RazorpayProvider, 'fetch_orders_by_receipt', lambda *args: [order_for(payment)])
    response = device_client(member, space).post(
        f'/api/v1/member/makerspaces/{space.pk}/payments/{payment.pk}/mobile-intent', format='json',
    )
    assert response.status_code == 200
    assert response.data == {
        'vendor': 'razorpay', 'payment_id': payment.pk, 'key_id': 'rzp_test_key',
        'order_id': 'order_mobile', 'amount_minor': 1250, 'currency': 'INR',
        'name': space.name, 'description': 'Paid service',
    }

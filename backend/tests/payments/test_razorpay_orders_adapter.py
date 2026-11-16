"""Provider error diagnostics stay private while enabling duplicate-receipt recovery."""

import io
import json
from urllib.error import HTTPError

import pytest

from apps.payments.providers.razorpay import RazorpayProvider, RazorpayRequestError
from apps.payments.resolution import PaymentSource


def test_http_error_surfaces_code_without_logging_provider_description(monkeypatch, caplog):
    source = PaymentSource('raw', 'secret-key', 'webhook-key', publishable_key='key-id', vendor='razorpay')
    payload = json.dumps({'error': {
        'code': 'BAD_REQUEST_ERROR', 'description': 'Receipt must be unique private-member-name',
    }}).encode()
    def rejected(*args, **kwargs):
        raise HTTPError('https://api.razorpay.com/v1/orders', 400, 'Bad request', {}, io.BytesIO(payload))
    monkeypatch.setattr('urllib.request.urlopen', rejected)

    with pytest.raises(RazorpayRequestError) as caught:
        RazorpayProvider().create_order(source, amount_minor=1250, currency='inr', receipt='sw-pay-1', notes={})

    assert caught.value.status == 400
    assert caught.value.code == 'BAD_REQUEST_ERROR'
    assert caught.value.is_duplicate_receipt
    assert 'private-member-name' in caught.value.description
    assert 'private-member-name' not in str(caught.value)
    assert 'private-member-name' not in caplog.text
    assert 'secret-key' not in caplog.text


@pytest.mark.parametrize('status,description', [(500, 'duplicate receipt'), (400, 'invalid amount')])
def test_unrelated_errors_are_not_duplicate_receipts(status, description):
    assert not RazorpayRequestError(status, 'BAD_REQUEST_ERROR', description).is_duplicate_receipt


def test_receipt_search_paginates_and_url_encodes(monkeypatch):
    provider, paths = RazorpayProvider(), []
    def request(source, method, path, body=None):
        paths.append(path)
        return {'items': [{}] * 100 if len(paths) == 1 else [{'id': 'order_last'}]}
    monkeypatch.setattr(provider, '_request', request)
    result = provider.fetch_orders_by_receipt(None, 'sw-pay-1&x')
    assert len(result) == 101
    assert 'receipt=sw-pay-1%26x' in paths[0]
    assert 'skip=100' in paths[1]

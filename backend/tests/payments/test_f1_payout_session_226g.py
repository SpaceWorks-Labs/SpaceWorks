"""Decision 226(g): payout money is session-only for the receipts-payments totals and native device grants."""
from types import SimpleNamespace

import pytest

from apps.accounts import native_session
from apps.operations.report_registry import REPORT_REGISTRY
from apps.payments.payout_session import full_session, is_payout_report


def _request(**fields):
    return SimpleNamespace(api_client=None, person_credential=None, user=SimpleNamespace(pk=7), **fields)


def test_receipts_payments_is_a_payout_report():
    assert is_payout_report(REPORT_REGISTRY["receipts-payments"])


def test_native_device_sessions_are_not_a_full_session():
    request = _request()
    assert full_session(request)
    token = native_session._NATIVE_USER_ID.set(7)
    try:
        assert not full_session(request)
    finally:
        native_session._NATIVE_USER_ID.reset(token)


def test_api_clients_and_person_credentials_are_still_refused():
    assert not full_session(SimpleNamespace(api_client=object(), person_credential=None, user=None))
    assert not full_session(SimpleNamespace(api_client=None, person_credential=object(), user=None))

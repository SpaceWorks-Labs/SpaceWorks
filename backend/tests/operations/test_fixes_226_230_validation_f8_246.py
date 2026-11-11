"""Decision 246 (lane F8): boundary and bad-input conditions for the 226-230 fixes.

Pure-function and monkeypatched checks only (no HTTP surface exists for these helpers): the previous-close
helper, the booking money summary, the payout-session predicate, the fix-URL builders, and the
space-currency field of the staff event payload.
"""
from datetime import datetime, timezone as tz
from decimal import Decimal
from types import SimpleNamespace

import pytest

from apps.bookings.response_money import booking_money
from apps.makerspaces.opening_hours import previous_close
from apps.makerspaces.platform import staff_payment_settings_url
from apps.payments.models import Payment
from apps.payments.payout_session import PAYOUT_REPORT_KEYS, full_session, is_payout_report, require_full_session
from tests.bookings.test_booking_response_money import _Booking, _NoPayments, _Payments

WEEK = {day: [{"start": "09:00", "end": "17:00"}] for day in ("monday", "tuesday", "wednesday", "thursday", "friday")}
SPACE = SimpleNamespace(timezone="UTC", opening_hours={"weekly": WEEK})


def _at(day, hour):
    return datetime(2026, 11, day, hour, 0, tzinfo=tz.utc)  # 2026-11-09 is a Monday


# 227 m14: previous_close boundaries -------------------------------------------------------

@pytest.mark.parametrize("days", [0, 1])
def test_a_window_too_short_to_reach_the_last_close_returns_none_not_a_guess(days):
    saturday = _at(14, 12)  # the last close is Friday 17:00, two days back
    assert previous_close(SPACE, saturday, days=days) is None


def test_exactly_the_closing_instant_is_closed_and_returns_itself_as_the_last_close():
    assert previous_close(SPACE, _at(9, 17)) == _at(9, 17)


def test_an_empty_weekly_schedule_or_missing_hours_means_always_open_not_an_error():
    assert previous_close(SimpleNamespace(timezone="UTC", opening_hours=None), _at(14, 12)) == _at(14, 12)
    assert previous_close(SimpleNamespace(timezone="UTC", opening_hours={"weekly": {}}), _at(14, 12)) == _at(14, 12)


# 226 booking response money: stored values are never trusted into a negative or blank amount ----

@pytest.mark.parametrize("snapshot", [{}, {"total": ""}, {"total": None}, {"total": "0"}, {"total": "-5.00"},
                                      {"currency": "usd"}])
def test_a_missing_zero_or_negative_frozen_quote_owes_nothing(monkeypatch, snapshot):
    monkeypatch.setattr("apps.bookings.response_money.charge_tracking_enabled", lambda *a: True)
    monkeypatch.setattr("apps.bookings.response_money.online_payments_enabled", lambda *a: True)
    monkeypatch.setattr("apps.bookings.response_money.Payment", _NoPayments)
    assert booking_money(_Booking(object(), snapshot))["amount_due"] is None


def test_a_quote_without_a_currency_reports_no_currency_rather_than_an_empty_string(monkeypatch):
    monkeypatch.setattr("apps.bookings.response_money.charge_tracking_enabled", lambda *a: True)
    monkeypatch.setattr("apps.bookings.response_money.online_payments_enabled", lambda *a: False)
    monkeypatch.setattr("apps.bookings.response_money.Payment", _NoPayments)
    result = booking_money(_Booking(object(), {"total": "4.00"}))
    assert result == {"amount_due": "4.00", "currency": None, "pay_online": False}


@pytest.mark.parametrize("status", [Payment.Status.PAID_ONLINE, Payment.Status.WAIVED, Payment.Status.PAID_OFFLINE])
def test_only_a_pending_payment_is_owed_whatever_the_settled_state(monkeypatch, status):
    monkeypatch.setattr("apps.bookings.response_money.charge_tracking_enabled", lambda *a: True)
    row = SimpleNamespace(status=status, amount=Decimal("9"), currency="usd")
    monkeypatch.setattr("apps.bookings.response_money.Payment", _Payments(row))
    assert booking_money(_Booking(object()))["amount_due"] is None


# 226g payout session predicate ---------------------------------------------------------------

def test_a_request_with_no_user_and_no_client_attributes_is_a_full_session():
    assert full_session(SimpleNamespace())


def test_require_full_session_refuses_with_a_typed_code():
    from rest_framework.exceptions import PermissionDenied
    with pytest.raises(PermissionDenied) as refused:
        require_full_session(SimpleNamespace(api_client=object()))
    assert refused.value.detail["code"] == "full_session_required"
    require_full_session(SimpleNamespace(api_client=None, person_credential=None, user=None))


def test_only_payout_keys_or_payout_columns_make_a_report_a_payout_report():
    assert all(is_payout_report(SimpleNamespace(key=key, fields=())) for key in PAYOUT_REPORT_KEYS)
    assert not is_payout_report(SimpleNamespace(key="members", fields=("name", "email")))
    assert is_payout_report(SimpleNamespace(key="other", fields=("amount", "payout_total")))


# 229/230 fix URLs ------------------------------------------------------------------------------

@pytest.mark.parametrize("outcome", ["success", "refresh", "failed"])
def test_the_stripe_return_url_carries_the_outcome_as_a_query_and_nothing_else(outcome):
    url = staff_payment_settings_url(SimpleNamespace(frontend_domain="", frontend_domain_status="", slug="lab"),
                                     outcome=outcome)
    assert url.endswith(f"/m/lab/admin/settings/money?stripe_connect={outcome}")
    assert url.count("?") == 1 and " " not in url

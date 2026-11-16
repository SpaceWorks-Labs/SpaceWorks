"""The public booking response reports what the server recorded as owed (audit row 30)."""
from decimal import Decimal

import pytest

from apps.bookings.response_money import booking_money
from apps.payments.models import Payment

pytestmark = pytest.mark.django_db


class _Space:
    def __init__(self, makerspace):
        self.makerspace = makerspace


class _Booking:
    pk = 1
    member_id = 7

    def __init__(self, makerspace, snapshot=None):
        self.space = _Space(makerspace)
        self.pricing_snapshot = snapshot or {}


def test_no_member_or_untracked_domain_owes_nothing(monkeypatch):
    monkeypatch.setattr("apps.bookings.response_money.charge_tracking_enabled", lambda *a: False)
    assert booking_money(_Booking(object())) == {"amount_due": None, "currency": None, "pay_online": False}
    booking = _Booking(object())
    booking.member_id = None
    assert booking_money(booking)["amount_due"] is None


def test_frozen_request_quote_is_reported_for_a_pending_booking(monkeypatch):
    monkeypatch.setattr("apps.bookings.response_money.charge_tracking_enabled", lambda *a: True)
    monkeypatch.setattr("apps.bookings.response_money.online_payments_enabled", lambda *a: True)
    monkeypatch.setattr("apps.bookings.response_money.Payment", _NoPayments)
    result = booking_money(_Booking(object(), {"total": "12.50", "currency": "USD"}))
    assert result == {"amount_due": "12.50", "currency": "usd", "pay_online": True}


def test_a_zero_quote_owes_nothing(monkeypatch):
    monkeypatch.setattr("apps.bookings.response_money.charge_tracking_enabled", lambda *a: True)
    monkeypatch.setattr("apps.bookings.response_money.Payment", _NoPayments)
    assert booking_money(_Booking(object(), {"total": "0.00", "currency": "usd"}))["amount_due"] is None


def test_settled_payment_owes_nothing(monkeypatch):
    monkeypatch.setattr("apps.bookings.response_money.charge_tracking_enabled", lambda *a: True)
    row = type("Row", (), {"status": Payment.Status.PAID_OFFLINE, "amount": Decimal("5"), "currency": "usd"})()
    monkeypatch.setattr("apps.bookings.response_money.Payment", _Payments(row))
    assert booking_money(_Booking(object()))["amount_due"] is None


class _NoPayments:
    Status = Payment.Status
    SubjectType = Payment.SubjectType

    class objects:
        @staticmethod
        def filter(**kwargs):
            return type("Q", (), {"first": staticmethod(lambda: None)})()


def _Payments(row):
    class P(_NoPayments):
        class objects:
            @staticmethod
            def filter(**kwargs):
                return type("Q", (), {"first": staticmethod(lambda: row)})()
    return P

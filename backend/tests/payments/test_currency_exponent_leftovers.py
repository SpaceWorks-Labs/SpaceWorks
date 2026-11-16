"""PY-7 (decision 268): event promo, refund, volunteer-credit and session-amount money rounds at the currency's
real exponent instead of a hard-coded hundredth. Pure arithmetic, no database."""
from decimal import Decimal
from types import SimpleNamespace

import pytest

from apps.events import orders_codes, orders_refunds
from apps.machines.serializers_sessions import MemberSessionSerializer
from apps.makerspaces import volunteer_credit


def _promo(**kw):
    base = dict(percent_off=0, amount_off=Decimal("0"), applies_per="order", ticket_type_id=None, max_uses=9, uses=0)
    return SimpleNamespace(**{**base, **kw})


def _rows(*nets):
    return [(i, SimpleNamespace(pk=1), 1, Decimal(n)) for i, n in enumerate(nets)]


def test_promo_split_over_three_seats_jpy_has_no_fractional_yen():
    promo = _promo(percent_off=10)
    discounts, _ = orders_codes.apply_promo(promo, _rows("1000", "1000", "1001"), "jpy")
    assert all(v == v.to_integral_value() for v in discounts.values())
    assert sum(discounts.values()) == Decimal("300")


def test_promo_kwd_keeps_two_rail_digits_and_usd_two():
    assert orders_codes._off(_promo(percent_off=33), Decimal("10.000"), "kwd") == Decimal("3.30")
    assert orders_codes._off(_promo(percent_off=33), Decimal("10.01"), "usd") == Decimal("3.30")
    assert orders_codes._off(_promo(percent_off=33), Decimal("10"), "jpy") == Decimal("3")


def test_per_seat_refund_rounds_down_at_currency_exponent():
    line = SimpleNamespace(line_total=Decimal("1000"), quantity=3, seats_per_unit=1,
                           order=SimpleNamespace(currency="jpy"))
    assert orders_refunds.seat_share(SimpleNamespace(line=line)) == Decimal("333")
    line.order.currency = "usd"
    assert orders_refunds.seat_share(SimpleNamespace(line=line)) == Decimal("333.33")


@pytest.mark.parametrize("currency,expected", [("jpy", Decimal("333")), ("usd", Decimal("333.33"))])
def test_volunteer_credit_reduce_charge_rounds_at_currency(currency, expected, monkeypatch):
    monkeypatch.setattr(volunteer_credit, "volunteer_on", lambda _space: True)
    monkeypatch.setattr(volunteer_credit, "available_credits",
                        lambda *_a: SimpleNamespace(select_for_update=lambda: SimpleNamespace(
                            order_by=lambda *_b: [])))
    net, used = volunteer_credit.reduce_charge(object(), object(), Decimal("1000"), currency, term_days=3)
    assert used == [] and net == Decimal("1000")
    assert volunteer_credit.quantize_money(Decimal("1000") / 3, currency) == expected


def test_session_running_amount_uses_snapshot_currency(monkeypatch):
    from apps.machines import serializers_sessions as mod
    monkeypatch.setattr(mod.billing, "final_quote", lambda *_a: SimpleNamespace(total=Decimal("12.5")))
    ser = MemberSessionSerializer()
    monkeypatch.setattr(ser, "_payment", lambda _o: None)
    monkeypatch.setattr(ser, "get_minutes", lambda _o: 10)
    obj = SimpleNamespace(billable=True, service_request_id=None, quote_snapshot={"currency": "jpy"})
    assert ser.get_amount(obj) == "13"

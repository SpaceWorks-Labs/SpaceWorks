"""F4 (decision 261): money stored at thousandths, charged at the provider's capturable precision.

JPY has no subunit, USD a hundredth, KWD a thousandth that the providers only accept in steps of
ten (the last digit must be 0). Quote -> charge -> capture -> refund -> receipt -> report must all
agree for each.
"""

from decimal import Decimal

import pytest

from apps.payments import stripe_client
from apps.payments.capture_flags import captured_amount
from apps.payments.models import Payment, PaymentDocument, Refund
from apps.payments.money import (
    MONEY, AmountNotCapturable, exponent_ok, money_text, quantize_money, rail_exponent, to_minor_units,
    to_provider_minor_units, trim_money,
)
from apps.payments.money_fields import MoneyField
from apps.payments.online_settlement import settle_capture
from apps.payments.refund_policy import precision_ok, round_down
from apps.payments.services_refunds import refund_payment
from apps.payments.tax.engine import q, tax_on
from tests.payments.recon_f_helpers import pending_charge
from tests.payments.test_models import configured_settings
from tests.payments.test_refunds import FakeStripe


def test_money_columns_are_three_decimals_wide():
    assert MONEY == {"max_digits": 13, "decimal_places": 3}
    for model in (Payment, Refund):
        field = model._meta.get_field("amount")
        assert (field.max_digits, field.decimal_places) == (13, 3)


@pytest.mark.parametrize("currency,exponent,rail", [("jpy", 0, 0), ("usd", 2, 2), ("kwd", 3, 2), ("bhd", 3, 2),
                                                    ("omr", 3, 2), ("jod", 3, 2), ("tnd", 3, 2)])
def test_exponents_and_the_charge_grid(currency, exponent, rail):
    from apps.payments.money import minor_unit_exponent
    assert minor_unit_exponent(currency) == exponent
    assert rail_exponent(currency) == rail


def test_one_rounding_rule_for_quote_charge_and_refund():
    assert q("1234.5", "jpy") == Decimal("1235")
    assert q("12.345", "usd") == Decimal("12.35")
    assert q("1.2345", "kwd") == Decimal("1.23")  # 10-fils grid: the provider cannot capture 1.234
    assert quantize_money("1.235", "kwd") == Decimal("1.24")
    assert tax_on(Decimal("10.000"), 500, inclusive=False, currency="kwd") == (
        Decimal("10.00"), Decimal("0.50"), Decimal("10.50"))
    assert precision_ok(Decimal("1.25"), "kwd") and not precision_ok(Decimal("1.255"), "kwd")
    assert not precision_ok(Decimal("1.5"), "jpy") and round_down(Decimal("1.9"), "jpy") == Decimal("1")


def test_provider_minor_units_refuse_what_the_provider_cannot_capture():
    assert to_provider_minor_units(Decimal("1.250"), "kwd") == 1250
    assert to_provider_minor_units(Decimal("12.35"), "usd") == 1235
    assert to_provider_minor_units(Decimal("1500"), "jpy") == 1500
    with pytest.raises(AmountNotCapturable):
        to_provider_minor_units(Decimal("1.255"), "kwd")  # last digit must be 0
    with pytest.raises(AmountNotCapturable):
        to_provider_minor_units(Decimal("12.345"), "usd")
    with pytest.raises(AmountNotCapturable):
        to_provider_minor_units(Decimal("1500.5"), "jpy")
    assert to_minor_units(Decimal("1.255"), "kwd") == 1255  # comparison helper still exact


def test_capture_amounts_must_sit_on_the_charge_grid():
    payment = Payment(currency="kwd", amount=Decimal("1.250"))
    assert captured_amount(1250, "kwd", payment) == Decimal("1.250")
    assert captured_amount(1255, "kwd", payment) is None


def test_values_read_like_they_always_did_unless_a_fils_is_present():
    assert str(trim_money(Decimal("12.350"))) == "12.35"
    assert str(trim_money(Decimal("1.255"))) == "1.255"
    assert money_text(Decimal("1500.000")) == "1500.00"
    assert money_text(Decimal("1.255")) == "1.255"
    assert exponent_ok(Decimal("1.255"), "kwd") and not exponent_ok(Decimal("1.255"), "usd")
    field = MoneyField()
    assert field.to_representation(Decimal("12.35")) == "12.35"
    assert field.to_representation(Decimal("1.255")) == "1.255"


@pytest.mark.django_db
@pytest.mark.parametrize("currency,amount,refund,minor_charge,minor_refund", [
    ("jpy", "1500", "500", 1500, 500),
    ("usd", "12.35", "5.10", 1235, 510),
    ("kwd", "1.250", "0.500", 1250, 500),
])
def test_quote_charge_capture_refund_receipt_report_agree(monkeypatch, currency, amount, refund, minor_charge,
                                                          minor_refund):
    space, staff, payment = pending_charge(f"f4-{currency}", amount=amount, currency=currency)
    configured_settings(space)
    FakeStripe.calls, FakeStripe.responses = [], [{"id": "re_1", "status": "succeeded"}]
    monkeypatch.setattr(stripe_client, "_stripe_module", lambda: FakeStripe)

    # quote: the engine's gross is exactly the charge
    assert q(amount, currency) == Decimal(amount)
    # charge -> capture at the provider's minor units
    assert to_provider_minor_units(payment.amount, currency) == minor_charge
    settle_capture(payment, provider=Payment.Provider.STRIPE, capture_id="pi_f4", event_id="evt_f4",
                   minor=minor_charge, currency=currency)
    payment.refresh_from_db()
    assert payment.status == Payment.Status.PAID_ONLINE
    # refund: the provider is told the refund in the same minor units
    done = refund_payment(payment, amount=Decimal(refund), reason="f4", actor=staff)
    assert FakeStripe.calls[0][0]["amount"] == minor_refund
    assert done.amount == Decimal(refund)
    # receipt and report show the same figure the ledger holds
    receipt = PaymentDocument.objects.filter(payment=payment, kind=PaymentDocument.Kind.RECEIPT).first()
    if receipt is not None:
        assert receipt.amount == Decimal(amount)
    assert Decimal(money_text(payment.amount)) == Decimal(amount)
    assert Refund.counted_total(payment) == Decimal(refund)


@pytest.mark.django_db
def test_a_refund_finer_than_the_charge_grid_is_refused_not_rounded(monkeypatch):
    from apps.payments.exceptions_refunds import RefundNotAllowed

    space, staff, payment = pending_charge("f4-refuse", amount="1.250", currency="kwd")
    configured_settings(space)
    monkeypatch.setattr(stripe_client, "_stripe_module", lambda: FakeStripe)
    FakeStripe.calls, FakeStripe.responses = [], []
    settle_capture(payment, provider=Payment.Provider.STRIPE, capture_id="pi_f4b", event_id="evt_f4b",
                   minor=1250, currency="kwd")
    payment.refresh_from_db()
    with pytest.raises(RefundNotAllowed):
        refund_payment(payment, amount=Decimal("0.255"), reason="too fine", actor=staff)
    assert not FakeStripe.calls

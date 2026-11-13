"""Converting a ledger amount into the integer a provider expects.

`Payment.amount` is a Decimal in MAJOR units. Both vendors take the currency's smallest
unit as an int, and that unit is not always a hundredth: a yen has no subunit and a
Kuwaiti dinar has a thousandth. Multiplying everything by 100 charged a JPY member 100x the
debt and refunded a KWD member a tenth of it. The exponent table is ISO 4217's, matching
Stripe's published zero-decimal and three-decimal lists.
"""

from decimal import ROUND_HALF_UP, Decimal

#: Every money column stores a thousandth (0.001), the finest ISO 4217 exponent in use (KWD, BHD,
#: OMR, JOD, TND). A USD or JPY value is just a 3-decimal value with trailing zeros, so widening the
#: column changed no row. `max_digits` is one wider than the old 12 so the integer part keeps its
#: ten digits. Models, serializers and migrations spell the pair out through this constant.
MONEY_DECIMAL_PLACES = 3
MONEY_MAX_DIGITS = 13
MONEY = {"max_digits": MONEY_MAX_DIGITS, "decimal_places": MONEY_DECIMAL_PLACES}

ZERO_DECIMAL = frozenset(
    {
        "bif", "clp", "djf", "gnf", "jpy", "kmf", "krw", "mga",
        "pyg", "rwf", "ugx", "vnd", "vuv", "xaf", "xof", "xpf",
    }
)
THREE_DECIMAL = frozenset({"bhd", "jod", "kwd", "omr", "tnd"})


def minor_unit_exponent(currency):
    code = (currency or "").lower()
    if code in ZERO_DECIMAL:
        return 0
    if code in THREE_DECIMAL:
        return 3
    return 2


def to_minor_units(amount, currency):
    """Integer minor units, rounded half-up. Never a float."""
    scale = Decimal(10) ** minor_unit_exponent(currency)
    return int((Decimal(amount) * scale).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def rail_exponent(currency=None):
    """Decimal places a charge may carry so every gateway can capture it exactly (decision 260).

    Stripe and Razorpay both require the last digit of a three-decimal currency (KWD, BHD, OMR,
    JOD, TND) to be 0, so an online charge moves in 10-fils steps even though the ledger stores
    fils. Zero- and two-decimal currencies use their real exponent. Quote, charge, receipt and
    report round ONCE, here, so they cannot disagree with what the provider will capture.
    """
    exponent = minor_unit_exponent(currency) if currency else 2
    return 2 if exponent == 3 else exponent


def quantum(currency=None):
    return Decimal(1).scaleb(-rail_exponent(currency))


def quantize_money(amount, currency=None, rounding=ROUND_HALF_UP):
    return Decimal(amount).quantize(quantum(currency), rounding=rounding)


class AmountNotCapturable(ValueError):
    """The amount carries a digit the provider cannot capture (a stray fils on KWD)."""


def to_provider_minor_units(amount, currency):
    """`to_minor_units` for a request that goes to Stripe or Razorpay: refuses an amount the
    provider would reject or round, instead of letting it round silently."""
    minor = to_minor_units(amount, currency)
    if Decimal(amount) != Decimal(minor).scaleb(-minor_unit_exponent(currency)):
        raise AmountNotCapturable("amount_not_capturable")
    if minor_unit_exponent(currency) == 3 and minor % 10:
        raise AmountNotCapturable("amount_not_capturable")
    return minor


def exponent_ok(amount, currency):
    """Whether `amount` has no digit finer than the currency's real minor unit (a yen, a fils)."""
    step = Decimal(1).scaleb(-minor_unit_exponent(currency))
    return Decimal(amount) == Decimal(amount).quantize(step)


def trim_money(value):
    """A stored thousandth shown the way a hundredth always was: 12.350 -> 12.35, 1.255 stays."""
    if value is None:
        return value
    value = Decimal(value)
    hundredths = value.quantize(Decimal("0.01"))
    if hundredths == value:
        return hundredths
    return value.quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)


def money_text(value):
    """Fixed-point text for exports: two places, three only when a fils is present."""
    return format(trim_money(value), "f")

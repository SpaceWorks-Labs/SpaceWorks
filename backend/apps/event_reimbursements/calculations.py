"""No network FX; integer budgets and explicit exponent-aware HALF_UP conversion."""

from decimal import Decimal, ROUND_HALF_UP, localcontext
import re

from apps.payments.event_payouts.validation import PayoutValidationError, minor


def convert_minor(*, original_minor, rate, source_exponent, target_exponent):
    """Exponents must come from G's supported_minor_unit_exponent helper.

    A rate is target MAJOR units per source MAJOR unit. Convert once at the
    individual line boundary; never round an aggregate or use binary floats.
    """
    minor(original_minor)
    if any(type(value) is not int or value not in {0, 2, 3} for value in (source_exponent, target_exponent)):
        raise PayoutValidationError("invalid_currency_exponent")
    if not isinstance(rate, str) or re.fullmatch(r"(?:0|[1-9][0-9]{0,11})(?:\.[0-9]{1,12})?", rate) is None:
        raise PayoutValidationError("invalid_fx_rate")
    parsed = Decimal(rate)
    if parsed <= 0:
        raise PayoutValidationError("invalid_fx_rate")
    with localcontext() as context:
        context.prec = 60
        result = int((Decimal(original_minor) * parsed * Decimal(10) ** (target_exponent - source_exponent))
                     .quantize(Decimal(1), rounding=ROUND_HALF_UP))
    return minor(result, zero=True)


def percentage_cap(*, estimate_minor, basis_points, cap_minor):
    minor(estimate_minor, zero=True)
    minor(cap_minor, zero=True)
    if type(basis_points) is not int or not 0 <= basis_points <= 10000:
        raise PayoutValidationError("invalid_percentage")
    # Integer HALF_UP for nonnegative values; no Decimal context or float drift.
    return min(cap_minor, (estimate_minor * basis_points + 5000) // 10000)

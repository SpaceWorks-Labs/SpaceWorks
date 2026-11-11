"""Serializer field for money (3 decimals on the wire, 2-decimal looking when exact).

The columns store a thousandth so KWD/BHD/OMR/JOD/TND keep their fils (`models.DecimalField(
**MONEY)`, see `money.MONEY`). A USD or JPY value is the same number with a trailing zero, so
the API hands it back as it always did ("12.35", not "12.350"): trimming happens only when the
third decimal is zero, never when it carries a fils.
"""

from decimal import Decimal

from rest_framework import serializers

from apps.payments.money import MONEY_DECIMAL_PLACES, MONEY_MAX_DIGITS, trim_money


class MoneyField(serializers.DecimalField):
    """DRF counterpart: validates at 3 places, renders "12.35" or "1.255"."""

    def __init__(self, **kwargs):
        kwargs.setdefault("max_digits", MONEY_MAX_DIGITS)
        kwargs.setdefault("decimal_places", MONEY_DECIMAL_PLACES)
        super().__init__(**kwargs)

    def to_internal_value(self, data):
        # "15.00" in, 15.00 out: str() of a validated amount (audit meta, notices) matches what is stored and shown.
        return trim_money(super().to_internal_value(data))

    def to_representation(self, value):
        rendered = super().to_representation(value)
        if isinstance(rendered, str):
            whole, dot, fraction = rendered.partition(".")
            if dot and len(fraction) == 3 and fraction.endswith("0"):
                return f"{whole}.{fraction[:2]}"
            return rendered
        return trim_money(rendered) if isinstance(rendered, Decimal) else rendered

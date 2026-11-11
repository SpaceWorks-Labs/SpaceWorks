"""Hack-money: an amount may not carry a digit finer than the space currency's minor unit.

The columns store thousandths for every currency; a yen or a rupee prize must still be a whole yen or a
whole paisa. A share below 0.01 is fine where the currency allows it (a dinar has fils).
"""

from decimal import Decimal

from django.utils.translation import gettext
from rest_framework.exceptions import ValidationError


def require_precision(field, amount, makerspace):
    from apps.payments.money import exponent_ok
    from .options import currency
    money = currency(makerspace)
    if amount is not None and not exponent_ok(Decimal(amount), money):
        raise ValidationError({field: gettext("Use an amount with no digit finer than the %(currency)s minor unit.")
                               % {"currency": money.upper()}})

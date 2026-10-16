"""Current consumable price basis shared by inventory and machine pools."""
from decimal import Decimal, InvalidOperation
from rest_framework.exceptions import ValidationError

# Unit factors use the pool's base unit; incompatible dimensions never convert.
UNITS = {
    "g": ("mass", Decimal(1)), "kilograms": ("mass", Decimal(1000)),
    "ml": ("volume", Decimal(1)), "l": ("volume", Decimal(1000)),
    "mm": ("length", Decimal(1)), "m": ("length", Decimal(1000)),
    "grams": ("mass", Decimal(1)), "kg": ("mass", Decimal(1000)),
    "milliliters": ("volume", Decimal(1)), "liters": ("volume", Decimal(1000)),
    "millimeters": ("length", Decimal(1)), "meters": ("length", Decimal(1000)),
    "count": ("count", Decimal(1)),
}


def validate_price(unit_cost, currency, cost_unit, measurement_unit):
    if unit_cost is None:
        if currency or cost_unit:
            raise ValidationError({"unit_cost": "A price is required with currency and cost unit."})
        return
    try:
        price = Decimal(str(unit_cost))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValidationError({"unit_cost": "Enter a valid price."}) from exc
    if not price.is_finite() or price < 0:
        raise ValidationError({"unit_cost": "Enter a non-negative price."})
    if not isinstance(currency, str) or len(currency) != 3 or not currency.isascii() or not currency.isalpha() or currency != currency.upper():
        raise ValidationError({"cost_currency": "Use a three-letter uppercase currency code."})
    if not isinstance(cost_unit, str) or cost_unit not in UNITS or measurement_unit not in UNITS or UNITS[cost_unit][0] != UNITS[measurement_unit][0]:
        raise ValidationError({"cost_unit": "Price unit must match the consumable's measurement dimension."})



def clean_model_price(instance, measurement_unit):
    """Django model forms use Django's validation errors rather than DRF's errors."""
    from django.core.exceptions import ValidationError as ModelValidationError
    try:
        validate_price(instance.unit_cost, instance.cost_currency, instance.cost_unit, measurement_unit)
    except ValidationError as exc:
        raise ModelValidationError(exc.detail) from exc

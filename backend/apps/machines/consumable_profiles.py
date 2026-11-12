"""Per-machine-type consumable profiles: the vocabulary and its validation (decision 341).

A profile row says what one machine type uses up on a job, in which unit, how it is
estimated at intake and who records the actual at completion. Units are a closed list so
a quote line, a stock debit and a report can never disagree about what "1" means.
"""

import re
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext, gettext_noop


class Kind(models.TextChoices):
    MATERIAL = "material", gettext_noop("Material stock")
    TOOL_WEAR = "tool_wear", gettext_noop("Tool wear")
    TIME = "time", gettext_noop("Time")
    PER_JOB = "per_job", gettext_noop("Fixed per job")
    OTHER = "other", gettext_noop("Other")


class Unit(models.TextChoices):
    GRAM = "g", "g"
    KILOGRAM = "kg", "kg"
    MILLIMETRE = "mm", "mm"
    METRE = "m", "m"
    MILLILITRE = "ml", "ml"
    LITRE = "l", "l"
    SQUARE_CM = "cm2", "cm²"
    SQUARE_M = "m2", "m²"
    CUBIC_CM = "cm3", "cm³"
    SHEET = "sheet", gettext_noop("sheet")
    PIECE = "piece", gettext_noop("piece")
    MINUTE = "min", "min"
    HOUR = "h", "h"
    USE = "use", gettext_noop("use")
    THOUSAND_STITCHES = "k_stitch", gettext_noop("1,000 stitches")


class EstimateBy(models.TextChoices):
    NONE = "none", gettext_noop("Not estimated")
    MEMBER = "member", gettext_noop("Member at intake")
    STAFF = "staff", gettext_noop("Staff when quoting")
    FILE = "file", gettext_noop("From the job file")


class Source(models.TextChoices):
    MEMBER = "member", gettext_noop("Member")
    STAFF = "staff", gettext_noop("Staff")
    ADAPTER = "adapter", gettext_noop("Machine adapter")
    FILE = "file", gettext_noop("Job file")


RECORDERS = ("staff", "member", "adapter")
ATTRIBUTES = ("material", "colour", "thickness", "size")
KEY_RE = re.compile(r"[a-z][a-z0-9_]{0,49}")
MAX_CHOICES = 100
MAX_QUANTITY = Decimal("1000000000")

# Profile unit -> (pool unit, factor). Only these may link to a consumable pool; the factor
# converts one profile unit into pool units (1 kg = 1000 grams, 1 cm³ = 1 ml).
POOL_UNITS = {
    "g": ("grams", Decimal(1)), "kg": ("grams", Decimal(1000)),
    "ml": ("milliliters", Decimal(1)), "l": ("milliliters", Decimal(1000)), "cm3": ("milliliters", Decimal(1)),
    "mm": ("millimeters", Decimal(1)), "m": ("millimeters", Decimal(1000)),
    "sheet": ("count", Decimal(1)), "piece": ("count", Decimal(1)), "use": ("count", Decimal(1)),
}
# Units counted in whole items: an inventory product link debits through Inventory Availability.
WHOLE_UNITS = frozenset({"sheet", "piece", "use"})


def validate_key(key):
    if not isinstance(key, str) or not KEY_RE.fullmatch(key) or key.endswith("_id"):
        raise ValidationError({"key": gettext("Use a short lowercase key (letters, digits, underscores).")})


def validate_attributes(value):
    """`{"material": ["PLA", "PETG"], "colour": []}`: an empty list means free text."""
    if not isinstance(value, dict) or set(value) - set(ATTRIBUTES):
        raise ValidationError({"attributes": gettext("Attributes may be material, colour, thickness or size.")})
    for name, choices in value.items():
        if (not isinstance(choices, list) or len(choices) > MAX_CHOICES
                or any(not isinstance(item, str) or not item.strip() or len(item) > 100 for item in choices)
                or len({item.casefold() for item in choices}) != len(choices)):
            raise ValidationError({"attributes": gettext("Each attribute needs unique choices (up to 100).")})


def validate_record_by(value):
    if not isinstance(value, list) or not value or set(value) - set(RECORDERS) or len(set(value)) != len(value):
        raise ValidationError({"record_by": gettext("Choose who records the actual: staff, member or adapter.")})


def validate_stock_link(unit, pool_unit=None, has_product=False):
    if pool_unit is not None and POOL_UNITS.get(unit, (None,))[0] != pool_unit:
        raise ValidationError({"consumable_pool": gettext("The stock pool's unit does not match this consumable.")})
    if has_product and unit not in WHOLE_UNITS:
        raise ValidationError({"product": gettext("Only sheet, piece or use consumables can draw inventory items.")})


def selected_attributes(definition_attributes, given):
    """Check a job's chosen attributes against the definition; returns the cleaned dict."""
    given = given or {}
    if not isinstance(given, dict) or set(given) - set(definition_attributes or {}):
        raise ValidationError({"attributes": gettext("This consumable does not take those attributes.")})
    cleaned = {}
    for name, value in given.items():
        if not isinstance(value, str) or not value.strip() or len(value) > 100:
            raise ValidationError({"attributes": gettext("Attribute values must be short text.")})
        choices = definition_attributes[name]
        if choices and value.casefold() not in {item.casefold() for item in choices}:
            raise ValidationError({"attributes": gettext("{name} is not one of the offered choices.").format(name=name)})
        cleaned[name] = value.strip()
    return cleaned


def parse_quantity(value, unit):
    from decimal import InvalidOperation
    try:
        quantity = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValidationError({"quantity": gettext("Enter a number.")}) from exc
    if isinstance(value, bool) or not quantity.is_finite() or quantity <= 0 or quantity > MAX_QUANTITY:
        raise ValidationError({"quantity": gettext("Enter a positive amount.")})
    quantity = quantity.quantize(Decimal("0.001"))
    if quantity <= 0:
        raise ValidationError({"quantity": gettext("Enter a positive amount.")})
    if unit in WHOLE_UNITS and quantity != quantity.to_integral_value():
        raise ValidationError({"quantity": gettext("Sheets, pieces and uses are whole numbers.")})
    return quantity

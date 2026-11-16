"""MOD-1B: the consumable price basis validator (money input) - every branch.

A price needs a three-letter UPPERCASE currency and a cost unit of the SAME dimension as the measurement unit
(mass with mass, volume with volume, length with length, count with count); a missing price allows no currency or
unit; negative, non-finite and non-numeric prices are refused. Both error flavours (DRF and Django forms) carry the field.
"""

from decimal import Decimal
from types import SimpleNamespace

import pytest
from django.core.exceptions import ValidationError as FormValidationError
from rest_framework.exceptions import ValidationError

from apps.inventory.cost_basis import UNITS, clean_model_price, validate_price


def refused(*args):
    with pytest.raises(ValidationError) as caught:
        validate_price(*args)
    return caught.value.detail


@pytest.mark.parametrize("currency, unit", [("", ""), ("USD", ""), ("", "g"), ("INR", "kg")])
def test_no_price_allows_no_currency_or_unit(currency, unit):
    if currency or unit:
        assert "unit_cost" in refused(None, currency, unit, "g")
    else:
        assert validate_price(None, currency, unit, "g") is None


@pytest.mark.parametrize("price", ["0", 0, "0.00", "12.345", Decimal("9999999.99"), 5])
def test_a_non_negative_numeric_price_with_a_matching_unit_is_accepted(price):
    assert validate_price(price, "USD", "kg", "g") is None


@pytest.mark.parametrize("price", ["abc", "", [], {}, "1,5", "NaN", "Infinity", "-Infinity"])
def test_a_non_numeric_or_non_finite_price_is_refused_on_unit_cost(price):
    assert "unit_cost" in refused(price, "USD", "g", "g")


@pytest.mark.parametrize("price", ["-0.01", -1, Decimal("-5")])
def test_a_negative_price_is_refused_on_unit_cost(price):
    assert str(refused(price, "USD", "g", "g")["unit_cost"]) == "Enter a non-negative price."


@pytest.mark.parametrize("currency", ["usd", "Usd", "US", "USDX", "U1D", "US$", "", None, 840, "ÜSD"])
def test_the_currency_must_be_three_uppercase_ascii_letters(currency):
    assert "cost_currency" in refused("1", currency, "g", "g")


@pytest.mark.parametrize("cost_unit, measurement", [
    ("g", "ml"), ("l", "g"), ("m", "kg"), ("count", "g"), ("g", "count"), ("unknown", "g"), ("g", "unknown"), (None, "g"), ("g", None), ("", ""),
])
def test_a_unit_of_another_dimension_or_an_unknown_unit_is_refused_on_cost_unit(cost_unit, measurement):
    assert "cost_unit" in refused("1", "USD", cost_unit, measurement)


def test_every_known_unit_pairs_with_every_unit_of_its_own_dimension():
    for cost_unit, (dimension, _factor) in UNITS.items():
        for measurement, (other, _f) in UNITS.items():
            if dimension == other:
                assert validate_price("1", "USD", cost_unit, measurement) is None, (cost_unit, measurement)
            else:
                assert "cost_unit" in refused("1", "USD", cost_unit, measurement), (cost_unit, measurement)


def test_the_form_flavour_raises_a_django_validation_error_carrying_the_field():
    good = SimpleNamespace(unit_cost="2.50", cost_currency="USD", cost_unit="kg", )
    assert clean_model_price(good, "g") is None
    bad = SimpleNamespace(unit_cost="2.50", cost_currency="usd", cost_unit="kg")
    with pytest.raises(FormValidationError) as caught:
        clean_model_price(bad, "g")
    assert "cost_currency" in caught.value.message_dict

from types import SimpleNamespace

import pytest
from django.core.exceptions import ValidationError

from apps.inventory.equipment_kit_validation import normalize_lines, public_safe


def product(*, maker=1, public=True, archived=False, consumable=False):
    return SimpleNamespace(makerspace_id=maker, is_public=public, is_archived=archived,
                           is_consumable=consumable)


def test_mixed_kit_projection_is_all_or_nothing_and_respects_consumables_gate():
    lines = [
        {"product_id": 1, "quantity_per_person": 1, "kind": "returnable"},
        {"product_id": 2, "quantity_per_person": 2, "kind": "consumable"},
    ]
    products = {1: product(), 2: product(consumable=True)}
    predicate = lambda item: item is products[1]
    assert public_safe(lines, products, 1, consumables_enabled=True, returnable_allowed=predicate)
    assert not public_safe(lines, products, 1, consumables_enabled=False, returnable_allowed=predicate)
    products[2].is_public = False
    assert not public_safe(lines, products, 1, consumables_enabled=True, returnable_allowed=predicate)
    products[2].is_public = True
    products[2].makerspace_id = 2
    assert not public_safe(lines, products, 1, consumables_enabled=True, returnable_allowed=predicate)


@pytest.mark.parametrize("quantity", [True, 0, 100, "1"])
def test_invalid_quantity_does_not_become_a_planned_line(quantity):
    with pytest.raises(ValidationError):
        normalize_lines([{"product_id": 1, "quantity_per_person": quantity, "kind": "returnable"}],
                        {1: product()}, 1)


def test_duplicate_or_wrong_kind_rejected():
    line = {"product_id": 1, "quantity_per_person": 1, "kind": "returnable"}
    with pytest.raises(ValidationError):
        normalize_lines([line, line], {1: product()}, 1)
    with pytest.raises(ValidationError):
        normalize_lines([line], {1: product(consumable=True)}, 1)


@pytest.mark.parametrize("kind", [[], {}])
def test_malformed_kind_fails_closed(kind):
    line = {"product_id": 1, "quantity_per_person": 1, "kind": kind}
    with pytest.raises(ValidationError):
        normalize_lines([line], {1: product()}, 1)
    assert not public_safe([line], {1: product()}, 1, consumables_enabled=True,
                           returnable_allowed=lambda _: True)

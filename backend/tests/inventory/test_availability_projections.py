"""Inventory Availability owns all quantity math, including the read-only projections Events uses.

`inventory.availability.outstanding_units` / `stock_warnings` replace the copies the events equipment desk
used to compute itself (Codex arch-1 #6). The desk behaviour is pinned over HTTP by
`tests/events/test_event_conflicts_machines_equipment.py`; these pin the projections and the ownership.
"""
import ast
from pathlib import Path
from types import SimpleNamespace

import pytest

from apps.inventory import availability
from apps.inventory.models import InventoryProduct
from tests.test_request_workflow import make_product, make_space

APPS = Path(__file__).resolve().parents[2] / "apps"


def _item(issued, returned=0, damaged=0, missing=0):
    return SimpleNamespace(issued_quantity=issued, returned_quantity=returned,
                           damaged_quantity=damaged, missing_quantity=missing)


def _request(*items):
    return SimpleNamespace(items=SimpleNamespace(all=lambda: list(items)))


def test_outstanding_units_counts_what_is_still_with_the_borrower():
    assert availability.outstanding_units(_request(_item(3, returned=1), _item(2, damaged=1, missing=1))) == 2


def test_outstanding_units_never_goes_negative_on_a_drifted_row():
    assert availability.outstanding_units(_request(_item(1, returned=3))) == 0


@pytest.mark.django_db
def test_stock_warnings_flag_repair_and_shortage_without_writing():
    space = make_space("proj-warn")
    product = make_product(space, total_quantity=5, available_quantity=2)
    InventoryProduct.objects.filter(pk=product.pk).update(needs_fix_quantity=1)
    product.refresh_from_db()
    before = InventoryProduct.objects.values("available_quantity", "reserved_quantity").get(pk=product.pk)
    codes = {(code, count) for _product, code, count in availability.stock_warnings({product.pk: product},
                                                                                    {product.pk: 3})}
    assert codes == {(availability_codes().repair, 1), (availability_codes().short, 3)}
    assert InventoryProduct.objects.values("available_quantity", "reserved_quantity").get(pk=product.pk) == before


@pytest.mark.django_db
def test_stock_warnings_are_empty_when_stock_covers_the_ask():
    space = make_space("proj-ok")
    product = make_product(space, total_quantity=5, available_quantity=5)
    assert availability.stock_warnings({product.pk: product}, {product.pk: 2}) == []
    assert availability.stock_warnings({}, {}) == []


@pytest.mark.django_db
def test_request_stock_warnings_sum_only_the_asks_awaiting_review():
    space = make_space("proj-asks")
    product = make_product(space, total_quantity=5, available_quantity=3)
    line = lambda qty: SimpleNamespace(product_id=product.pk, product=product, requested_quantity=qty)  # noqa: E731
    held = [_request(line(5))]
    asking = [_request(line(2)), _request(line(2))]
    assert [(code, count) for _p, code, count in availability.request_stock_warnings(held, asking)] == [
        (availability_codes().short, 4)]
    assert availability.request_stock_warnings(held, [_request(line(3))]) == []


def availability_codes():
    from apps.inventory import availability_projections as p
    return SimpleNamespace(repair=p.UNITS_UNDER_REPAIR, short=p.INSUFFICIENT_STOCK)


@pytest.mark.parametrize("relative", ["events/equipment_desk_warnings.py", "events/equipment_desk.py"])
def test_events_desk_reads_no_stock_counter_itself(relative):
    """Events may copy counters into a row, never do arithmetic or comparisons on stock counters."""
    tree = ast.parse((APPS / relative).read_text(encoding="utf-8"))
    math = [node for node in ast.walk(tree) if isinstance(node, (ast.BinOp, ast.Compare, ast.AugAssign))]
    attrs = {inner.attr for node in math for inner in ast.walk(node) if isinstance(inner, ast.Attribute)}
    counters = {"available_quantity", "reserved_quantity", "needs_fix_quantity", "issued_quantity",
                "returned_quantity", "damaged_quantity", "missing_quantity", "requested_quantity"}
    assert not attrs & counters, attrs & counters

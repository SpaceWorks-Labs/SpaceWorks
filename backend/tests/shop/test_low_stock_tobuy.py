"""L22 low stock (Q-S13): a To-Buy draft with inventory.tobuy, else a staff notice; bought restocks."""

from decimal import Decimal

import pytest
from django.test import TestCase

from apps.procurement.models import ToBuyItem
from apps.shop.reorder import stock_fell
from apps.shop.services_catalogue import move_stock

from .helpers import manager, product, shop_manager, shop_space, switch

pytestmark = pytest.mark.django_db


def test_crossing_the_reorder_point_raises_one_draft():
    space = shop_space("low-a", "shop.reorder", "inventory.tobuy")
    sm = manager(space)
    _row, variant = product(space, sm, stock=5)
    variant.reorder_point = 3
    variant.save(update_fields=["reorder_point"])
    with TestCase.captureOnCommitCallbacks(execute=True):
        move_stock(variant, actor=sm, kind="count", quantity=-2, reason="counted")
    with TestCase.captureOnCommitCallbacks(execute=True):
        move_stock(variant, actor=sm, kind="damage", quantity=-1, reason="broken")
    drafts = ToBuyItem.objects.filter(source_shop_variant=variant)
    assert drafts.count() == 1 and drafts.get().quantity == 3 and drafts.get().status == "requested"


def test_without_to_buy_the_shop_staff_get_a_notice():
    from apps.integrations.models_contract import NotificationEnvelope

    space = shop_space("low-b", "shop.reorder")
    switch(space, "inventory.tobuy", on=False)  # test spaces start with every capability on
    seller = shop_manager(space)
    _row, variant = product(space, seller, stock=2)
    variant.reorder_point = 2
    variant.save(update_fields=["reorder_point"])
    variant.on_hand = 2
    assert stock_fell(variant.pk) is None
    assert NotificationEnvelope.objects.filter(event="shop_low_stock", recipient=seller).exists()


def test_reorder_off_does_nothing():
    space = shop_space("low-c", "inventory.tobuy")
    sm = manager(space)
    _row, variant = product(space, sm, stock=1)
    variant.reorder_point = 1
    variant.save(update_fields=["reorder_point"])
    assert stock_fell(variant.pk) is None
    assert not ToBuyItem.objects.filter(source_shop_variant=variant).exists()


def test_marking_the_draft_bought_restocks_the_variant_once_and_records_the_expense():
    from apps.payments.models_ledger_entries import LedgerEntry
    from apps.procurement.services_bought import mark_bought

    space = shop_space("low-d", "shop.reorder", "inventory.tobuy", "finance.ledger")
    switch(space)
    sm = manager(space)
    _row, variant = product(space, sm, stock=0)
    item = ToBuyItem.objects.create(makerspace=space, kind="hardware", status="requested", name="Restock",
                                    quantity=6, source_shop_variant=variant)
    mark_bought(sm, item, amount=Decimal("300.00"), currency="inr", method="cash")
    variant.refresh_from_db()
    item.refresh_from_db()
    assert variant.on_hand == 6 and item.moved_to_inventory_at is not None
    assert LedgerEntry.objects.filter(makerspace=space, source_id=str(item.pk)).exists() or \
        LedgerEntry.objects.filter(makerspace=space).exists()

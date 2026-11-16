"""Received purchase handoffs and bought ledger: exact stock/link/money effects."""
from decimal import Decimal

import pytest

from apps.inventory.models import InventoryProduct
from apps.machines.models import Machine, MachineConsumable, MachineType
from apps.payments.models_ledger_entries import LedgerEntry
from apps.procurement.models import ToBuyItem
from tests.machines.route_support_cx11b_g2 import command, prove, world

pytestmark = [pytest.mark.django_db, pytest.mark.area_inventory, pytest.mark.area_machines]
CASES = [("inventory", "inventory.tobuy"), ("printer", "machines.tobuy"), ("printer", "machines"),
         ("printer", "machine_service"), ("spool", "machines.tobuy"), ("spool", "machine_service"),
         ("refill", "machines.tobuy"), ("refill", "machines"), ("bought", "inventory.tobuy")]
CASES += [("inventory", "loans.enabled"), ("bought", "loans.enabled")]


@pytest.mark.parametrize("native", [False, True], ids=["browser", "native"])
@pytest.mark.parametrize("operation,key", CASES)
def test_stock_handoff_changes_the_exact_subject_after_restore(native, operation, key):
    w = world(native)
    hardware = operation in {"inventory", "bought"}
    kind = MachineType.objects.get(makerspace__isnull=True, slug="3d_printer") if operation in {"printer", "spool"} else w.machine_type
    item = ToBuyItem.objects.create(makerspace=w.space, kind="hardware" if hardware else "printing",
        machine_type=None if hardware else kind, name="Retained purchase", quantity=2,
        status="requested" if operation == "bought" else "received")
    name = {"inventory": "to-buy-move-to-inventory", "printer": "to-buy-move-to-printing",
            "spool": "to-buy-move-to-printing", "refill": "to-buy-refill-consumable", "bought": "to-buy-mark-bought"}[operation]
    if operation == "inventory":
        product = InventoryProduct.objects.create(makerspace=w.space, name="Retained stock", available_quantity=4, total_quantity=4)
        body = {"mode": "topup", "quantity": 3, "product_id": product.pk}
        audit = ("inventory.quantity_adjusted", "procurement.moved_to_inventory")
    elif operation == "refill":
        consumable = MachineConsumable.objects.create(machine=w.machine, measurement="grams", label="Resin", remaining=5)
        item.source_consumable = consumable
        item.save(update_fields=["source_consumable"])
        body, audit = {"amount": "7"}, ("procurement.consumable_refilled",)
    elif operation == "bought":
        body = {"amount": "12.00", "currency": "inr", "method": "cash", "reference": "G2-CASH", "vendor_name": "Supplier"}
        audit = ("ledger.expense_recorded", "procurement.bought")
    else:
        body = {"target": operation, "name": "New G2 printer", "model": "G2 model"} if operation == "printer" else {
            "target": "spool", "material": "PLA", "color": "Blue", "initial_weight_grams": "100", "remaining_weight_grams": "90"}
        audit = ("procurement.moved_to_printing",)

    def check(response):
        item.refresh_from_db()
        assert response.data["id"] == item.pk
        if operation == "inventory":
            product.refresh_from_db()
            assert (product.available_quantity, product.total_quantity, item.resulting_product_id) == (7, 7, product.pk)
            assert item.moved_to_inventory_at is not None
        elif operation == "refill":
            consumable.refresh_from_db()
            assert consumable.remaining == Decimal("12")
            assert item.moved_to_inventory_at is not None
        elif operation == "bought":
            entry = LedgerEntry.objects.get(source_kind="procurement.to_buy", source_id=str(item.pk))
            assert (entry.amount, entry.currency, entry.method, entry.reference, entry.domain) == (
                Decimal("12"), "inr", "cash", "G2-CASH", "inventory")
            assert (item.status, item.actual_unit_cost, item.purchaser_id) == ("received", Decimal("6"), w.actor.pk)
        elif operation == "printer":
            saved = Machine.objects.get(pk=item.resulting_machine_id)
            assert (saved.name, saved.machine_type_id, saved.type_payload) == ("New G2 printer", kind.pk, {"model": "G2 model"})
            assert item.moved_to_inventory_at is not None
        else:
            pool = item.resulting_pool
            assert (pool.material, pool.color, pool.initial_grams, pool.remaining_grams) == (
                "PLA", "Blue", Decimal("100"), Decimal("90"))
            assert item.moved_to_inventory_at is not None

    # The item resolver conceals a disabled stream as not_found. Additional
    # destination modules refuse with their module code only after standing.
    off = "module_disabled" if key == "machine_service" else "not_found"
    prove(w, key, lambda c: command(c, f"procurement:{name}", "post", [item.pk], body), check,
          audits=audit, off=(404, off))

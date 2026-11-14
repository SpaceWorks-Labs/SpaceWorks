"""Bought receipts in both streams, including the independent saved-vendor capability."""
from decimal import Decimal

import pytest

from apps.payments.models_ledger_entries import LedgerEntry
from apps.procurement.models import ToBuyItem, Vendor
from tests.machines.route_support_cx11b_g2 import command, prove, world

pytestmark = [pytest.mark.django_db, pytest.mark.area_inventory, pytest.mark.area_machines]
CASES = [("hardware", "inventory.tobuy"), ("hardware", "inventory.vendors"),
         ("printing", "machines.tobuy"), ("printing", "machines"), ("printing", "inventory.vendors"),
         ("hardware", "loans.enabled")]


@pytest.mark.parametrize("native", [False, True], ids=["browser", "native"])
@pytest.mark.parametrize("kind,key", CASES)
def test_mark_bought_checks_stream_and_vendor_independently_and_records_exact_receipt(native, kind, key):
    w = world(native)
    vendor = Vendor.objects.create(makerspace=w.space, name="Retained supplier")
    item = ToBuyItem.objects.create(makerspace=w.space, kind=kind, name="New blades", quantity=3,
                                   machine_type=w.machine_type if kind == "printing" else None)

    def check(response):
        item.refresh_from_db()
        entry = LedgerEntry.objects.get(source_kind="procurement.to_buy", source_id=str(item.pk))
        assert (item.status, item.vendor_id, item.vendor_name, item.actual_unit_cost) == (
            "received", vendor.pk, "Retained supplier", Decimal("10"))
        assert (entry.amount, entry.currency, entry.method, entry.reference, entry.counterparty,
                entry.domain, entry.machine_type_id) == (
            Decimal("30"), "inr", "cash", "G2-BOUGHT", "Retained supplier",
            "machines" if kind == "printing" else "inventory", w.machine_type.pk if kind == "printing" else None)
        assert response.data["id"] == item.pk
        assert LedgerEntry.objects.filter(source_kind="procurement.to_buy", source_id=str(item.pk)).count() == 1

    # 481/494 object scope resolves before switches; saved vendor admission is a
    # further command dependency, not permission to disclose another tenant's item.
    prove(w, key, lambda c: command(c, "procurement:to-buy-mark-bought", "post", [item.pk],
          {"amount": "30", "currency": "inr", "method": "cash", "reference": "G2-BOUGHT", "vendor_id": vendor.pk}),
          check, audits=("ledger.expense_recorded", "procurement.bought"),
          off=(404, "capability_disabled" if key == "inventory.vendors" else "not_found"))

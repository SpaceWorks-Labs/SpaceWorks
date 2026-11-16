"""#94: marking a To-Buy item bought records an L5 expense, links the vendor and restocks."""

from decimal import Decimal

import pytest

from apps.audit.models import AuditLog
from apps.machines.models import Machine, MachineConsumable, MachineType
from apps.makerspaces.models import MakerspaceMembership
from apps.payments.models_ledger_entries import LedgerEntry
from apps.procurement.models import ToBuyItem, Vendor
from tests.return_helpers import authenticated_client, make_member, make_product, make_space, make_user

pytestmark = pytest.mark.django_db
FEATURES = {"inventory.tobuy", "machines.tobuy", "inventory.vendors"}


def space_with(slug, features=FEATURES):
    space = make_space(slug)
    space.enabled_features = sorted(set(space.enabled_features or []) | set(features))
    space.save(update_fields=["enabled_features"])
    return space


def url(item):
    return f"/api/v1/procurement/to-buy/{item.pk}/mark-bought"


def test_inventory_manager_marks_bought_once_and_stock_goes_up():
    space = space_with("bought-inv")
    manager = make_member("bought-inv-im", space, MakerspaceMembership.Role.INVENTORY_MANAGER)
    product = make_product(space, name="Glue", available_quantity=2, total_quantity=2, is_consumable=True)
    vendor = Vendor.objects.create(makerspace=space, name="Glue Co")
    item = ToBuyItem.objects.create(makerspace=space, kind="hardware", name="Glue", quantity=10,
                                    source_product=product)
    body = {"amount": "45.50", "method": "upi", "reference": "UPI-1", "vendor_id": vendor.pk}
    response = authenticated_client(manager).post(url(item), body, format="json")
    assert response.status_code == 200, response.content
    item.refresh_from_db()
    product.refresh_from_db()
    assert (item.status, item.vendor_id, item.vendor_name) == ("received", vendor.pk, "Glue Co")
    assert item.actual_unit_cost == Decimal("4.55")
    assert product.available_quantity == 12
    entry = LedgerEntry.objects.get(source_kind="procurement.to_buy", source_id=str(item.pk))
    assert (entry.kind, entry.domain, entry.category, entry.amount, entry.counterparty) == (
        "expense", "inventory", "to_buy", Decimal("45.50"), "Glue Co")
    assert AuditLog.objects.filter(action="procurement.bought", target_id=str(item.pk)).count() == 1
    again = authenticated_client(manager).post(url(item), body, format="json")
    assert again.status_code == 400
    assert LedgerEntry.objects.filter(source_kind="procurement.to_buy").count() == 1


def test_machine_rows_need_the_machine_manager_and_land_in_machines_domain():
    space = space_with("bought-mach")
    laser = MachineType.objects.get(makerspace__isnull=True, slug="laser_cutter")
    machine = Machine.objects.create(makerspace=space, machine_type=laser, name="Laser")
    row = MachineConsumable.objects.create(machine=machine, measurement="grams", label="Wax",
                                           remaining=Decimal("5"), low_threshold=Decimal("10"))
    item = ToBuyItem.objects.create(makerspace=space, kind="printing", name="Wax", quantity=1,
                                    machine_type=laser, source_consumable=row)
    inventory_manager = make_member("bought-mach-im", space, MakerspaceMembership.Role.INVENTORY_MANAGER)
    body = {"amount": "12.00", "method": "cash", "refill_amount": "100"}
    assert authenticated_client(inventory_manager).post(url(item), body, format="json").status_code in (403, 404)
    space_manager = make_member("bought-mach-sm", space)  # an unlinked Machine Manager reaches no printing rows
    response = authenticated_client(space_manager).post(url(item), body, format="json")
    assert response.status_code == 200, response.content
    row.refresh_from_db()
    assert row.remaining == Decimal("105")
    entry = LedgerEntry.objects.get(source_kind="procurement.to_buy", source_id=str(item.pk))
    assert (entry.domain, entry.machine_type_id, entry.account) == ("machines", laser.pk, "cash")


def test_grams_restock_needs_a_refill_amount_and_members_are_refused():
    space = space_with("bought-refuse")
    laser = MachineType.objects.get(makerspace__isnull=True, slug="laser_cutter")
    machine = Machine.objects.create(makerspace=space, machine_type=laser, name="Laser")
    row = MachineConsumable.objects.create(machine=machine, measurement="grams", label="Wax",
                                           remaining=Decimal("5"), low_threshold=Decimal("10"))
    item = ToBuyItem.objects.create(makerspace=space, kind="printing", name="Wax", quantity=1,
                                    source_consumable=row)
    manager = make_member("bought-refuse-sm", space)
    response = authenticated_client(manager).post(url(item), {"amount": "3", "method": "cash"}, format="json")
    assert response.status_code == 400
    assert not LedgerEntry.objects.exists()
    item.refresh_from_db()
    assert item.status == "requested"
    member = make_user("bought-refuse-member", access_status="active")
    assert authenticated_client(member).post(url(item), {"amount": "3", "method": "cash"},
                                             format="json").status_code in (401, 403, 404)


def test_switch_off_hides_the_row_and_vendor_list():
    space = space_with("bought-off", {"inventory.tobuy"})
    space.enabled_features = [key for key in space.enabled_features if key not in ("machines.tobuy", "inventory.vendors")]
    space.save(update_fields=["enabled_features"])
    manager = make_member("bought-off-sm", space)
    item = ToBuyItem.objects.create(makerspace=space, kind="printing", name="Spool", quantity=1)
    assert authenticated_client(manager).post(url(item), {"amount": "1", "method": "cash"},
                                              format="json").status_code == 404
    vendors = f"/api/v1/procurement/makerspace/{space.pk}/vendors"
    assert authenticated_client(manager).get(vendors).status_code == 404

"""Decision 254: the Inventory area switch (`loans.enabled`) removes every inventory API surface.

The core models and rows stay installed; while the switch is off each inventory-only module
answers the typed `module_disabled` 404 even when it is installed, and machine consumables
(machine-scoped supplies, `staff_admin` + `inventory.consumables`) keep working.
"""
import pytest

from apps.inventory.models import InventoryProduct
from apps.makerspaces.loan_visibility import INVENTORY_ONLY_MODULES
from apps.makerspaces.platform import module_enabled
from tests.modules.family_helpers import account, client, family_space

pytestmark = pytest.mark.django_db

ADD_ONS = ("containers", "stocktake", "stock_transfers")


def _paths(space):
    base = f"/api/v1/admin/makerspace/{space.id}"
    return [f"{base}/inventory", f"{base}/categories", f"{base}/containers", f"{base}/stocktakes",
            f"{base}/stock-transfers", "/api/v1/admin/ledger"]


@pytest.mark.parametrize("loans", [True, False])
def test_inventory_routes_follow_the_switch(loans):
    space = family_space(f"inv254-{loans}", *ADD_ONS, "member_accounts", loans=loans)
    staff = client(account(f"inv254-staff-{loans}", staff=True))
    for path in _paths(space):
        response = staff.get(path, {"makerspace": space.id})
        if loans:
            assert response.status_code != 404 or response.data.get("code") != "module_disabled", path
        else:
            assert response.status_code == 404, path
            assert response.data.get("code") in {"module_disabled", "feature_disabled"}, path


def test_modules_stay_installed_but_answer_off_then_return_on_switch_back():
    space = family_space("inv254-roundtrip", *ADD_ONS, loans=True)
    product = InventoryProduct.objects.create(makerspace=space, name="Drill", total_quantity=2, available_quantity=2)
    assert all(module_enabled(space, key) for key in ADD_ONS)
    space.enabled_features.remove("loans.enabled")
    space.save(update_fields=["enabled_features"])
    assert set(ADD_ONS) <= set(space.enabled_modules) | {"containers", "stocktake", "stock_transfers"}
    assert not any(module_enabled(space, key) for key in INVENTORY_ONLY_MODULES)
    assert InventoryProduct.objects.filter(pk=product.pk).exists()
    space.enabled_features.append("loans.enabled")
    space.save(update_fields=["enabled_features"])
    assert all(module_enabled(space, key) for key in ADD_ONS)


def test_machine_consumables_keep_working_with_inventory_off():
    space = family_space("inv254-consumables", "machines", loans=False)
    if "inventory.consumables" not in space.enabled_features:
        space.enabled_features.append("inventory.consumables")
        space.save(update_fields=["enabled_features"])
    response = client(account("inv254-cons-staff", staff=True)).get(f"/api/v1/admin/makerspace/{space.id}/consumables")
    assert response.status_code == 200

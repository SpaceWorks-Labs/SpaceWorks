"""MOD-2: the consumable stock-options route (pools and item search) with scope, limits and switches."""

import pytest
from django.urls import reverse

from apps.inventory.models import InventoryProduct
from apps.machines.models import MachineConsumablePool
from tests.machines.test_machine_scope_surfaces import client_for, lab  # noqa: F401  (fixture)
from tests.return_helpers import make_member, make_product, make_space

pytestmark = pytest.mark.django_db


def _url(space, machine_type):
    return reverse("machine-type-consumable-stock", args=[space.pk, machine_type.pk])


def _pool(space, label, **scope):
    return MachineConsumablePool.objects.create(
        makerspace=space, material=label, initial_grams="100", remaining_grams="42.5", **scope)


def test_lists_pools_for_the_type_and_shared_ones_but_not_other_types(lab):  # noqa: F811
    own = _pool(lab["space"], "Own type", machine_type=lab["printer_type"])
    shared = _pool(lab["space"], "Shared")
    bound = _pool(lab["space"], "Bound printer", machine=lab["printer"])
    other = _pool(lab["space"], "Laser only", machine_type=lab["laser_type"])
    inactive = _pool(lab["space"], "Retired", machine_type=lab["printer_type"])
    MachineConsumablePool.objects.filter(pk=inactive.pk).update(is_active=False)
    response = client_for(lab["printer_mgr"]).get(_url(lab["space"], lab["printer_type"]))
    assert response.status_code == 200
    ids = {row["id"] for row in response.json()["pools"]}
    assert ids == {own.pk, shared.pk, bound.pk} and other.pk not in ids and inactive.pk not in ids
    assert response.json()["products"] == []  # no search term, no items


def test_scope_refuses_a_manager_of_another_type_and_a_foreign_tenant(lab):  # noqa: F811
    assert client_for(lab["laser_mgr"]).get(_url(lab["space"], lab["printer_type"])).status_code == 403
    stranger_space = make_space("stock-stranger")
    stranger = make_member("stock-stranger-sm", stranger_space)
    assert client_for(stranger).get(_url(lab["space"], lab["printer_type"])).status_code in (403, 404)


def test_item_search_is_capped_at_20_trimmed_and_tenant_scoped(lab):  # noqa: F811
    space = lab["space"]
    for index in range(25):
        InventoryProduct.objects.create(makerspace=space, name=f"Filament {index:02d}", total_quantity=1,
                                        available_quantity=1)
    other_space = make_space("stock-other-items")
    make_product(other_space, name="Filament foreign")
    viewer = client_for(make_member("stock-space-manager", space))
    response = viewer.get(_url(space, lab["printer_type"]), {"q": "  filament  "})
    names = [row["name"] for row in response.json()["products"]]
    assert response.status_code == 200 and len(names) == 20 and "Filament foreign" not in names
    assert names == sorted(names)
    # Over-long and markup queries are bounded, never errors.
    assert viewer.get(_url(space, lab["printer_type"]), {"q": "<script>" + "x" * 500}).status_code == 200
    assert viewer.get(_url(space, lab["printer_type"]), {"q": "حديد 🔩"}).json()["products"] == []


def test_machines_module_off_answers_404_and_signed_out_is_refused(lab):  # noqa: F811
    from rest_framework.test import APIClient
    from tests.module_helpers import disable_module
    assert APIClient().get(_url(lab["space"], lab["printer_type"])).status_code in (401, 403)
    disable_module(lab["space"], "machines")
    response = client_for(lab["printer_mgr"]).get(_url(lab["space"], lab["printer_type"]))
    assert response.status_code == 404 and response.json()["code"] == "module_disabled"

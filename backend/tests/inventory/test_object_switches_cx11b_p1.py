"""Parentless inventory capabilities keep stock and private warranty rows."""
import pytest
from tests.modules.test_switch_matrix_objects_rest_isolation import cx11b_isolated_phase  # noqa: F401
from django.urls import reverse

from apps.inventory.models import InventoryAsset
from apps.warranty.models import Warranty
from tests.inventory.test_consumables_unified import seed, url
from tests.inventory.switch_support_cx11b_p1 import prove_route, staff_outsiders
from tests.modules.switch_matrix_object_helpers import client_for

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.area_inventory]


@pytest.mark.parametrize("native", [False, True], ids=["browser", "native"])
def test_consumable_switch_restores_retained_stock_on_both_transports(native):
    space, actor, item, grams, pool = seed("p1-consumables")
    prove_route(space, client_for(actor, space, native), {"item": item, "grams": grams, "pool": pool},
                "inventory.consumables", lambda c: c.get(url(space)), off=(404, "capability_disabled"), outsiders=staff_outsiders(native))


@pytest.mark.parametrize("native", [False, True], ids=["browser", "native"])
@pytest.mark.parametrize("key", ["inventory.warranty", "loans.enabled"])
def test_inventory_warranty_switch_keeps_the_asset_and_supplier(native, key):
    space, actor, item, _, _ = seed("p1-warranty")
    space.enabled_features = sorted(set(space.enabled_features) | {"inventory.warranty"})
    space.save(update_fields=["enabled_features"])
    asset = InventoryAsset.objects.create(makerspace=space, product=item, asset_tag="P1-1")
    warranty = Warranty.objects.create(makerspace=space, asset=asset, vendor_name="Retained supplier")
    path = reverse("admin-asset-warranty", kwargs={"pk": asset.pk})
    prove_route(space, client_for(actor, space, native), {"asset": asset, "warranty": warranty},
                key, lambda c: c.get(path), off=(404, "capability_disabled"), outsiders=staff_outsiders(native))

pytestmark = ([pytestmark] if not isinstance(pytestmark, list) else pytestmark) + [
    pytest.mark.usefixtures("cx11b_isolated_phase")]

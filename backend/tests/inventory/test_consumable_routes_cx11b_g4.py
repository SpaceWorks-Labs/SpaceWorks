"""Staff inventory supply routes prove quantities, adjustment receipts and procurement drafts."""
import pytest
from django.urls import reverse

from apps.accounts.models import User
from apps.inventory.equipment_kit_services import create_template
from apps.inventory.models_equipment_proposals import EquipmentConsumablePlan
from apps.operations.models import InventoryAdjustment
from apps.procurement.models import ToBuyItem
from tests.modules.switch_matrix_object_helpers import object_world
from tests.operations.route_support_cx11b_g4 import contains, cycle, outsider, send
from tests.return_helpers import make_product

pytestmark = [pytest.mark.django_db, pytest.mark.area_inventory]

CASES = [("admin-consumables", "GET", "inventory.consumables"),
         ("admin-consumables", "GET", "staff_admin"),
         ("admin-consumable-use", "POST", "inventory.consumables"),
         ("admin-consumable-use", "POST", "staff_admin"),
         ("admin-consumable-equipment-sources", "GET", "inventory.consumables"),
         ("admin-consumable-equipment-sources", "GET", "staff_admin"),
         ("admin-reorder-suggestions", "GET", "public_inventory"),
         ("admin-reorder-suggestions", "GET", "loans.enabled"),
         ("admin-reorder-draft", "POST", "public_inventory"),
         ("admin-reorder-draft", "POST", "loans.enabled"),
         ("admin-reorder-draft", "POST", "inventory.tobuy")]


@pytest.mark.parametrize("native", [False, True], ids=["browser", "native"])
@pytest.mark.parametrize("name,method,key", CASES)
def test_inventory_supply_route_effect_and_retention(native, name, method, key):
    space, client, _ = object_world(native)
    actor = User.objects.get(username="sx-real-object-manager")
    product = make_product(space, name="Retained glue", is_consumable=True, total_quantity=4,
                           available_quantity=4, reorder_point=5, reorder_quantity=12, supplier="Retained supplier")
    _, version = create_template(actor=actor, makerspace_id=space.pk, name="Glue plan",
        lines=[{"product_id": product.pk, "kind": "consumable", "quantity_per_person": 2}])
    plan = EquipmentConsumablePlan.objects.create(makerspace=space, borrower=actor, kit_version=version, lines=version.lines)
    kwargs = {"makerspace_id": space.pk}
    if name in {"admin-consumable-use", "admin-consumable-equipment-sources"}:
        kwargs["pk"] = product.pk
    url = reverse(name, kwargs=kwargs)
    body = {"quantity": 3, "note": "Workshop"} if name == "admin-consumable-use" else {"product_id": product.pk} if method == "POST" else {}

    def check(response):
        product.refresh_from_db()
        if name == "admin-consumable-use":
            assert (product.available_quantity, product.total_quantity, response.data["remaining"]) == (1, 1, "1")
            adjustment = InventoryAdjustment.objects.get(product=product)
            assert (adjustment.delta_available, adjustment.delta_damaged, adjustment.delta_lost,
                    adjustment.created_by_id, adjustment.reason) == (-3, 0, 0, actor.pk, "Consumable used: Workshop")
        elif name == "admin-reorder-draft":
            draft = ToBuyItem.objects.get(pk=response.data["id"])
            assert (draft.source_product_id, draft.quantity, draft.kind, draft.vendor_name,
                    draft.status) == (product.pk, 12, "hardware", "Retained supplier", "requested")
            assert ToBuyItem.objects.filter(makerspace=space).count() == 1
        elif name == "admin-consumable-equipment-sources":
            assert response.data["results"] == [{"kind": "plan", "id": plan.pk, "planned_quantity": 2, "used_quantity": 0}]
        else:
            contains(response, product.pk)
            assert response.data["results"][0]["name"] == "Retained glue"

    audit = ("inventory.quantity_adjusted",) if name == "admin-consumable-use" else ("procurement.item_added",) if name == "admin-reorder-draft" else ()
    capability = key in {"inventory.consumables", "inventory.tobuy"}
    foreign = outsider(native)
    cycle(space, key, lambda: send(client, method, url, body), check,
          on=(201 if name == "admin-reorder-draft" else 200, None),
          off=(404, "capability_disabled" if capability else "module_disabled"),
          refusal_key="public_inventory" if key == "loans.enabled" else key,
          foreign=lambda: send(foreign, method, url, body), foreign_native=native, audit=audit)

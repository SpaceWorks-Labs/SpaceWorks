from uuid import uuid4

import pytest

from apps.accounts import rbac
from apps.encryption.preparation import prepare_tenants
from apps.inventory import equipment_use_service
from apps.inventory.models_equipment_proposals import EquipmentConsumablePlan, EquipmentKitTemplate, EquipmentKitVersion
from apps.operations.models import InventoryAdjustment
from tests.encryption.conftest import enabled_encryption
from tests.rbac_f6_helpers import custom_actor
from tests.return_helpers import authenticated_client, make_product, make_space


@pytest.mark.django_db(transaction=True)
def test_edit_only_linked_use_ack_survives_immediate_archive(monkeypatch):
    maker = make_space("linked-use-edit-only")
    maker.enabled_features = sorted(set(maker.enabled_features or []) | {"inventory.consumables"})
    maker.save(update_fields=["enabled_features"])
    actor = custom_actor(maker, ["edit_inventory"], name="linked-use-edit-only-actor")
    assert rbac.can(actor, rbac.Action.EDIT_INVENTORY, maker.pk)
    # Fixed roles: the role carrying edit_inventory (Inventory Manager) also views inventory, so no view-less actor exists.
    product = make_product(maker, is_consumable=True, available_quantity=10, total_quantity=10)
    template = EquipmentKitTemplate.objects.create(makerspace=maker, name="Kit", published_for_contexts=True)
    lines = [{"product_id": product.pk, "quantity_per_person": 2, "kind": "consumable"}]
    version = EquipmentKitVersion.objects.create(template=template, version=1, name="Kit", lines=lines)
    plan = EquipmentConsumablePlan.objects.create(makerspace=maker, borrower=actor, kit_version=version, lines=lines)
    original = equipment_use_service.linked_use

    def consume_then_archive(**kwargs):
        result = original(**kwargs)
        type(product).objects.filter(pk=product.pk).update(is_archived=True)
        return result

    monkeypatch.setattr(equipment_use_service, "linked_use", consume_then_archive)
    with enabled_encryption(), prepare_tenants([maker.pk]):
        response = authenticated_client(actor).post(
            f"/api/v1/admin/makerspace/{maker.pk}/consumables/{product.pk}/use",
            {"operation_id": str(uuid4()), "plan_id": plan.pk, "quantity": 2, "note": "used"}, format="json",
        )
    assert response.status_code == 200, response.content
    assert response.json() == {"status": "recorded", "replayed": False}
    product.refresh_from_db()
    assert product.is_archived and product.available_quantity == 8
    assert InventoryAdjustment.objects.filter(makerspace=maker, product=product, delta_available=-2).count() == 1

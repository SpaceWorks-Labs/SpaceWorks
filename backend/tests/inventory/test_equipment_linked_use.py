from uuid import uuid4

import pytest

from apps.encryption.preparation import prepare_tenants
from apps.inventory import equipment_use_service as service
from apps.inventory.models_equipment_proposals import (
    EquipmentConsumablePlan, EquipmentConsumableUseReceipt, EquipmentKitTemplate, EquipmentKitVersion,
)
from apps.operations.models import InventoryAdjustment
from tests.encryption.conftest import enabled_encryption
from tests.return_helpers import make_product, make_space, make_user


@pytest.mark.django_db(transaction=True)
def test_linked_use_replays_one_real_adjustment_and_conflicts_on_changed_quantity(monkeypatch):
    maker = make_space("linked-use")
    actor = make_user("linked-use-actor")
    product = make_product(maker, is_consumable=True, available_quantity=10, total_quantity=10)
    template = EquipmentKitTemplate.objects.create(makerspace=maker, name="Kit", published_for_contexts=True)
    lines = [{"product_id": product.pk, "quantity_per_person": 2, "kind": "consumable"}]
    version = EquipmentKitVersion.objects.create(template=template, version=1, name="Kit", lines=lines)
    plan = EquipmentConsumablePlan.objects.create(makerspace=maker, borrower=actor, kit_version=version, lines=lines)
    for name in ("assert_write_allowed", "assert_mapped_write_allowed", "require_module_locked",
                 "require_capability", "require_action"):
        monkeypatch.setattr(service, name, lambda *_: None)
    monkeypatch.setattr(service, "require_module", lambda *_: None)
    monkeypatch.setattr(service, "_preflight_source", lambda *_: None)
    operation = uuid4()
    args = dict(actor=actor, makerspace_id=maker.pk, product_id=product.pk, operation_id=operation,
                source_kind="plan", source_id=plan.pk, quantity=2, note="used")
    with enabled_encryption(), prepare_tenants([maker.pk]):
        _, adjustment, replayed = service.linked_use(**args)
        assert replayed is False
        _, again, replayed = service.linked_use(**args)
        assert replayed is True and again.pk == adjustment.pk
        with pytest.raises(service.UseConflict, match="operation_conflict"):
            service.linked_use(**{**args, "quantity": 3})
    product.refresh_from_db()
    assert product.available_quantity == 8
    assert InventoryAdjustment.objects.filter(pk=adjustment.pk, product=product, delta_available=-2).count() == 1
    assert EquipmentConsumableUseReceipt.objects.filter(makerspace=maker, operation_id=operation).count() == 1

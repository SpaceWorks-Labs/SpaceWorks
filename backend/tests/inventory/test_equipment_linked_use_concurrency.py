from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

import pytest
from django.db import close_old_connections

from apps.accounts.models import User
from apps.encryption.tenant_preparation import prepare_tenant_key
from apps.inventory.equipment_use_service import UseConflict, linked_use
from apps.inventory.models_equipment_proposals import EquipmentConsumablePlan, EquipmentConsumableUseReceipt, EquipmentKitTemplate, EquipmentKitVersion
from apps.operations.models import InventoryAdjustment
from apps.tenant_migration.gate_runtime import boundary_tenant_write
from tests.encryption.conftest import enabled_encryption
from tests.rbac_f6_helpers import custom_actor
from tests.return_helpers import make_product, make_space


@pytest.mark.django_db(transaction=True)
def test_concurrent_same_uuid_creates_one_canonical_adjustment():
    maker = make_space("linked-use-concurrent")
    maker.enabled_features = sorted(set(maker.enabled_features or []) | {"inventory.consumables"})
    maker.save(update_fields=["enabled_features"])
    actor = custom_actor(maker, ["edit_inventory"], name="linked-concurrent-actor")
    product = make_product(maker, is_consumable=True, available_quantity=10, total_quantity=10)
    template = EquipmentKitTemplate.objects.create(makerspace=maker, name="Kit", published_for_contexts=True)
    lines = [{"product_id": product.pk, "quantity_per_person": 2, "kind": "consumable"}]
    version = EquipmentKitVersion.objects.create(template=template, version=1, name="Kit", lines=lines)
    plan = EquipmentConsumablePlan.objects.create(makerspace=maker, borrower=actor, kit_version=version, lines=lines)
    operation, barrier = uuid4(), Barrier(2)
    arguments = dict(makerspace_id=maker.pk, product_id=product.pk, operation_id=operation,
                     source_kind="plan", source_id=plan.pk, quantity=2, note="use")

    def send():
        close_old_connections()
        try:
            principal = User.objects.get(pk=actor.pk)
            barrier.wait(timeout=10)
            try:
                return linked_use(actor=principal, **arguments)[2]
            except UseConflict as exc:
                assert str(exc) == "lock_busy"
                return "busy"
        finally:
            close_old_connections()

    with enabled_encryption():
        with boundary_tenant_write(maker.pk):
            prepare_tenant_key(maker.pk)
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: send(), range(2)))
        if "busy" in results:
            assert linked_use(actor=User.objects.get(pk=actor.pk), **arguments)[2] is True
    product.refresh_from_db()
    assert product.available_quantity == 8
    assert EquipmentConsumableUseReceipt.objects.filter(makerspace=maker, operation_id=operation).count() == 1
    assert InventoryAdjustment.objects.filter(makerspace=maker, product=product, delta_available=-2).count() == 1

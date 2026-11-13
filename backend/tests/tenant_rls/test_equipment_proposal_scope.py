import pytest

from apps.tenant_rls.scope_registry import predicates


@pytest.mark.django_db
def test_equipment_models_are_covered_by_scoped_policy():
    scope = predicates()
    assert scope["inventory.EquipmentKitVersion"].any_paths == ("template__makerspace",)
    for label in ("inventory.EquipmentKitTemplate", "inventory.EquipmentConsumablePlan",
                  "inventory.EquipmentKitAllocation", "inventory.EquipmentProposalReceipt", "inventory.EquipmentConsumableUseReceipt",
                  "events.EventConsumablePlanContext", "bookings.BookingConsumablePlanContext"):
        assert scope[label].any_paths == ("makerspace",)
        assert not scope[label].includes({"makerspace": 2}, 1)

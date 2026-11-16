import pytest

from apps.tenant_migration.insertion_errors import ArchiveFormatError
from apps.tenant_migration.semantic_equipment_proposals import remap


@pytest.mark.parametrize("label", ["inventory.EquipmentKitVersion", "inventory.EquipmentConsumablePlan", "inventory.EquipmentKitAllocation"])
def test_snapshot_products_are_remapped_without_mutating_source(label):
    source = {"lines": [{"product_id": 7, "quantity_per_person": 2, "kind": "consumable"}]}
    row = dict(source)
    assert remap(label, source, row, lambda model, pk: {("inventory.InventoryProduct", 7): 19}[(model, pk)])
    assert row["lines"] == [{"product_id": 19, "quantity_per_person": 2, "kind": "consumable"}]
    assert source["lines"][0]["product_id"] == 7


@pytest.mark.parametrize("lines", [[], [{"product_id": True, "quantity_per_person": 1, "kind": "consumable"}], [{"product_id": 1, "quantity_per_person": 1, "kind": "consumable", "secret": "x"}]])
def test_invalid_snapshots_refuse_import(lines):
    with pytest.raises(ArchiveFormatError):
        remap("inventory.EquipmentKitVersion", {}, {"lines": lines}, lambda _model, value: value)


def test_missing_mapping_fails_closed():
    row = {"lines": [{"product_id": 9, "quantity_per_person": 1, "kind": "returnable"}]}
    def missing(_model, _value):
        raise ArchiveFormatError("Missing archive product.")
    with pytest.raises(ArchiveFormatError):
        remap("inventory.EquipmentKitAllocation", {}, row, missing)

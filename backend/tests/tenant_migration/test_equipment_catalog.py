from apps.data_export.classification_equipment_proposals import DATASETS, FIELDS
from apps.tenant_migration.catalog_equipment_proposals import FIELD_NAMES, JSON_FIELDS, PROJECTED_LABELS


def test_all_pinned_models_have_matching_literal_portable_fields():
    assert set(FIELDS) == set(FIELD_NAMES) == set(DATASETS) == PROJECTED_LABELS
    assert all(set(names.split()) == FIELD_NAMES[label] for label, names in FIELDS.items())
    assert JSON_FIELDS == {(label, "lines") for label in (
        "inventory.EquipmentKitVersion", "inventory.EquipmentConsumablePlan", "inventory.EquipmentKitAllocation")}


def test_cross_tenant_snapshot_edges_are_not_exported():
    predicate = DATASETS["inventory.EquipmentKitAllocation"][1]
    assert predicate.includes({"makerspace": 1, "request__makerspace": 1, "kit_version__template__makerspace": 1}, 1)
    assert not predicate.includes({"makerspace": 1, "request__makerspace": 2, "kit_version__template__makerspace": 1}, 1)
    assert not predicate.includes({"makerspace": 1, "request__makerspace": 1, "kit_version__template__makerspace": 2}, 1)

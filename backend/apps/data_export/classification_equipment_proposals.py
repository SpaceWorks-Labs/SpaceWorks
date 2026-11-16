"""Pinned core equipment-kit export fields and ownership edges."""
from .types import TenantPredicate as P

FIELDS = {
    "inventory.EquipmentKitTemplate": "id makerspace name revision current_version published_for_contexts archived created_at updated_at",
    "inventory.EquipmentKitVersion": "id template version name lines created_at",
    "inventory.EquipmentConsumablePlan": "id makerspace borrower kit_version lines created_at",
    "inventory.EquipmentKitAllocation": "id makerspace request kit_version lines created_at",
    "inventory.EquipmentProposalReceipt": "id makerspace borrower creator operation_id fingerprint_version payload_sha256 intent_snapshot intent_version outcome_kind imported_nonreplayable request consumable_plan created_at",
    "inventory.EquipmentConsumableUseReceipt": "id makerspace operation_id creator product quantity payload_sha256 intent_snapshot intent_version imported_nonreplayable allocation plan adjustment created_at",
    "events.EventConsumablePlanContext": "id makerspace plan event participant_registration active revision created_at updated_at",
    "bookings.BookingConsumablePlanContext": "id makerspace plan booking active revision created_at updated_at",
}
DATASETS = {
    "inventory.EquipmentKitTemplate": ("inventory/equipment_kit_templates.csv", P(("makerspace",))),
    "inventory.EquipmentKitVersion": ("inventory/equipment_kit_versions.csv", P(("template__makerspace",))),
    "inventory.EquipmentConsumablePlan": ("inventory/equipment_consumable_plans.csv", P(("makerspace",), ("kit_version__template__makerspace",))),
    "inventory.EquipmentKitAllocation": ("inventory/equipment_kit_allocations.csv", P(("makerspace",), ("request__makerspace", "kit_version__template__makerspace"))),
    "inventory.EquipmentProposalReceipt": ("inventory/equipment_proposal_receipts.csv", P(("makerspace",), ("request__makerspace", "consumable_plan__makerspace"))),
    "inventory.EquipmentConsumableUseReceipt": ("inventory/equipment_consumable_use_receipts.csv", P(("makerspace",), ("product__makerspace", "allocation__makerspace", "plan__makerspace", "adjustment__makerspace"))),
    "events.EventConsumablePlanContext": ("events/consumable_plan_contexts.csv", P(("makerspace",), ("plan__makerspace", "event__makerspace", "participant_registration__event__makerspace"))),
    "bookings.BookingConsumablePlanContext": ("bookings/consumable_plan_contexts.csv", P(("makerspace",), ("plan__makerspace", "booking__space__makerspace"))),
}

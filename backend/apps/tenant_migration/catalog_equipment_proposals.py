"""Portable core snapshot pinned to models_equipment_proposals.py 6edd8cd2."""
FIELD_NAMES = {
    "inventory.EquipmentKitTemplate": frozenset("id makerspace name revision current_version published_for_contexts archived created_at updated_at".split()),
    "inventory.EquipmentKitVersion": frozenset("id template version name lines created_at".split()),
    "inventory.EquipmentConsumablePlan": frozenset("id makerspace borrower kit_version lines created_at".split()),
    "inventory.EquipmentKitAllocation": frozenset("id makerspace request kit_version lines created_at".split()),
    "inventory.EquipmentProposalReceipt": frozenset("id makerspace borrower creator operation_id fingerprint_version payload_sha256 intent_snapshot intent_version outcome_kind imported_nonreplayable request consumable_plan created_at".split()),
    "inventory.EquipmentConsumableUseReceipt": frozenset("id makerspace operation_id creator product quantity payload_sha256 intent_snapshot intent_version imported_nonreplayable allocation plan adjustment created_at".split()),
    "events.EventConsumablePlanContext": frozenset("id makerspace plan event participant_registration active revision created_at updated_at".split()),
    "bookings.BookingConsumablePlanContext": frozenset("id makerspace plan booking active revision created_at updated_at".split()),
}
PROJECTED_LABELS = frozenset(FIELD_NAMES)
JSON_FIELDS = frozenset((label, "lines") for label in (
    "inventory.EquipmentKitVersion", "inventory.EquipmentConsumablePlan", "inventory.EquipmentKitAllocation"))

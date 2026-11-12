"""Explicit WP4 field/model review, independent of other build lanes."""

EXPORTED_MODEL_FIELDS = {
    "machines.MachineMaterial": "id makerspace machine_type name colours is_active",
    "operations.StocktakePolicy": "id makerspace blind_default variance_threshold",
    "operations.StocktakeSchedule": "id makerspace container name interval_days next_due blind is_active",
    # Decisions 341/343: per-type consumable profiles, their job usage and space machine-type templates.
    "machines.MachineTypeConsumable": "id makerspace machine_type key name kind unit attributes required estimate_by record_by unit_price consumable_pool product position is_active template_key created_at updated_at",
    "machines.ServiceRequestConsumableUsage": "id makerspace service_request definition key name kind unit phase quantity attributes source unit_price device_ref created_at",
    "machines.MachineTypeSetup": "id makerspace machine_type booking_slot_minutes booking_buffer_before_minutes booking_buffer_after_minutes booking_approval_mode training_notes notes_at_session_start notes_at_job_request updated_at",
    "machines.MachineTypeDocument": "id makerspace machine_type title object_key original_filename content_type size_bytes member_visible created_at",
    "machines.MachineTypeTemplate": "id makerspace key name description category icon based_on spec is_active created_at updated_at",
}
FIELD_ADDITIONS = {
    "inventory.InventoryProduct": "borrowing_terms",
    "machines.Machine": "status_since public_fields",
    "machines.MachineType": "intake_schema",
    "operations.StocktakeSession": "blind variance_threshold approval_required",
    "maintenance.MaintenanceSchedule": "trigger usage_hours job_count meter_started_at",
}
OMITTED_MODELS = {
    "inventory.InventoryWatch": "Source personal delivery subscriptions do not become target disclosure authority.",
    "maintenance.MaintenanceCalendarFeed": "Deployment-local bearer authority; staff reissue a feed after import.",
}
NON_REFERENCE_JSON_FIELDS = frozenset({
    ("machines.Machine", "public_fields"),
    ("machines.MachineType", "intake_schema"),
    ("machines.MachineMaterial", "colours"),
    ("machines.MachineTypeConsumable", "attributes"),
    ("machines.MachineTypeConsumable", "record_by"),
    ("machines.ServiceRequestConsumableUsage", "attributes"),
    ("machines.MachineTypeTemplate", "spec"),
})


def exported_fields(base):
    return {**{label: names + (" " + FIELD_ADDITIONS[label] if label in FIELD_ADDITIONS else "")
               for label, names in base.items()}, **EXPORTED_MODEL_FIELDS}

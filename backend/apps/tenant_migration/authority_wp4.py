from .tenant_dump_types import AuthorityDisposition as D, authority


def fields(label, names, disposition):
    return tuple(((label, name), authority(disposition,
                 "WP4 tenant data retains target module, feature and actor gates.")) for name in names.split())


AUTHORITY_ENTRIES = (
    *fields("inventory.InventoryProduct", "borrowing_terms", D.PRESERVE),
    *fields("inventory.InventoryWatch", "makerspace product user ready_at notified_at", D.DROP),
    *fields("maintenance.MaintenanceCalendarFeed", "makerspace user token_digest token_hint revoked_at", D.DROP),
    *fields("machines.Machine", "status_since", D.PRESERVE),
    *fields("machines.Machine", "public_fields", D.RESET),
    *fields("machines.MachineType", "intake_schema", D.PRESERVE),
    *fields("machines.MachineMaterial", "makerspace machine_type name colours is_active", D.PRESERVE),
    *fields("operations.StocktakePolicy", "makerspace blind_default", D.PRESERVE),
    *fields("operations.StocktakePolicy", "variance_threshold", D.RESET),
    *fields("operations.StocktakeSchedule", "makerspace container name interval_days next_due blind", D.PRESERVE),
    *fields("operations.StocktakeSchedule", "is_active", D.RESET),
    *fields("operations.StocktakeSession", "blind", D.PRESERVE),
    *fields("operations.StocktakeSession", "variance_threshold approval_required", D.RESET),
    *fields("maintenance.MaintenanceSchedule", "trigger usage_hours job_count meter_started_at", D.PRESERVE),
    *fields("machines.MachineTypeConsumable", "makerspace machine_type key name kind unit attributes required estimate_by record_by unit_price consumable_pool product position is_active template_key created_at updated_at", D.PRESERVE),
    *fields("machines.ServiceRequestConsumableUsage", "makerspace service_request definition key name kind unit phase quantity attributes source unit_price created_at", D.PRESERVE),
    *fields("machines.ServiceRequestConsumableUsage", "device_ref", D.RESET),
    *fields("machines.MachineTypeSetup", "makerspace machine_type booking_slot_minutes booking_buffer_before_minutes booking_buffer_after_minutes booking_approval_mode training_notes notes_at_session_start notes_at_job_request updated_at", D.PRESERVE),
    *fields("machines.MachineTypeDocument", "makerspace machine_type title object_key original_filename content_type size_bytes member_visible created_at", D.PRESERVE),
    *fields("machines.MachineTypeTemplate", "makerspace key name description category icon based_on spec is_active created_at updated_at", D.PRESERVE),
)

AUTHORITY_FIELDS = {edge: rule.reason for edge, rule in AUTHORITY_ENTRIES}

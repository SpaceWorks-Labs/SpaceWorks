from .target_projection_types import TargetField, ForeignKeyPolicy, ReferenceDisposition, RowPolicy, RowDisposition

ROW_POLICIES = {
    label: RowPolicy(RowDisposition.DROP, "Source subscriptions and bearer authority are reissued on target.")
    for label in ("inventory.InventoryWatch", "maintenance.MaintenanceCalendarFeed")
}

FIELD_PROJECTION = {
    ("machines.Machine", "public_fields"): TargetField([], reason="Target staff authorize optional public disclosures."),
    ("operations.StocktakePolicy", "variance_threshold"): TargetField(None, reason="Target staff choose approval thresholds."),
    ("operations.StocktakeSession", "variance_threshold"): TargetField(None, reason="Retain mandatory target approval."),
    ("operations.StocktakeSession", "approval_required"): TargetField(True, reason="Imported variance cannot waive target review."),
    ("operations.StocktakeSchedule", "is_active"): TargetField(False, reason="Target staff re-enable scheduled work."),
    ("machines.ServiceRequestConsumableUsage", "device_ref"): TargetField(
        "", reason="Adapter devices are source-deployment enrolments; provenance stays in the source audit."),
}
FK_POLICIES = {
    ("machines.MachineMaterial", "machine_type"): ForeignKeyPolicy(ReferenceDisposition.REMAP_RESOLVED, "Resolve the built-in/custom type mapping."),
    ("machines.MachineTypeConsumable", "machine_type"): ForeignKeyPolicy(ReferenceDisposition.REMAP_RESOLVED, "Resolve the built-in/custom type mapping."),
    ("machines.MachineTypeSetup", "machine_type"): ForeignKeyPolicy(ReferenceDisposition.REMAP_RESOLVED, "Resolve the built-in/custom type mapping."),
    ("machines.MachineTypeDocument", "machine_type"): ForeignKeyPolicy(ReferenceDisposition.REMAP_RESOLVED, "Resolve the built-in/custom type mapping."),
}

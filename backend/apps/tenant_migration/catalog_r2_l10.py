"""Release-2 lane L10: tenant-dump field snapshot of the two machine-integration models.

Both are OMITTED from exports (data_export `classification_r2_l10` gives each reason), so
neither travels in a tenant dump: a moved device re-enrolls and is re-bound on its target.
"""

FIELD_NAMES = {
    "devices.MachineTypeIntegration": frozenset(
        "id makerspace machine_type kind enabled config_schema_version created_by created_at updated_at".split()),
    "devices.PrinterStatusSnapshot": frozenset(
        "device makerspace schema_version state progress_percent layer_current layer_total nozzle_temp_c "
        "bed_temp_c chamber_temp_c spools clear_token observed_at received_at".split()),
}

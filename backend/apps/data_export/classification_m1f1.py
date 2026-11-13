"""Reviewed tracking facts and deployment-only provider history."""

EXPORTED_FIELDS = {
    "inventory.InventoryStockSnapshot": "id makerspace product local_day available issued total out_of_stock below_reorder",
    "machines.MachineStatusEvent": "id makerspace machine from_status to_status at source",
    "machines.ConsumableCostRecord": "id makerspace source_kind source_id quantity measurement_unit unit_price_minor_per_measurement_unit cost_total_minor currency recorded_at",
}
FIELD_ADDITIONS = {
    "machines.MachineUsageEntry": "member started_at",
    "machines.MachineConsumablePool": "unit_cost cost_currency cost_unit",
    "inventory.InventoryProduct": "unit_cost cost_currency cost_unit",
}
OMITTED_MODELS = {
    "accounts.DeviceActivityDay": "Runtime grant activity; target sessions start with no history.",
    "accounts.WebSessionActivityDay": "Runtime browser-session activity; target sessions start with no history.",
    "accounts.ChannelUsageDay": "Deployment-local channel/area call counts; no person, never portable.",
    "accounts.AttestationVerificationLog": "Anonymous deployment attestation outcomes, not tenant data.",
    "integrations.PushDeliveryAttempt": "Runtime staff push delivery to source-local devices; never portable.",
    "integrations.SmsSendLog": "Runtime provider outcomes; deployment history does not travel.",
    "integrations.EmailProviderEvent": "Deployment-local webhook replay identity; never portable.",
}

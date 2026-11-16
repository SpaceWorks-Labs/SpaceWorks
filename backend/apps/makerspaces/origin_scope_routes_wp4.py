MAKERSPACE_ROUTES = {
    name: "makerspace_id" for name in (
        "stocktake-policy", "stocktake-schedules", "stocktake-schedule-detail",
        "machine-materials", "machine-material-detail", "machine-type-intake",
        "maintenance-feed", "maintenance-feed-calendar",
        # Decisions 341/343.
        "machine-type-consumables", "machine-type-consumable-detail", "machine-type-consumable-stock",
        "machine-type-templates", "machine-type-template-detail", "machine-type-template-apply",
        "admin-machine-job-consumables",
        "machine-type-setup", "machine-type-booking-defaults-apply", "machine-type-documents",
        "machine-type-document-presign", "machine-type-document-detail",
    )
}

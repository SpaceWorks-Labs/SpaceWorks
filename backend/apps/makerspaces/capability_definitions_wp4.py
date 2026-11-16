"""WP4 opt-ins; defaults preserve existing tenant behavior."""


def definitions(feature):
    return (
        feature("inventory.notify_when_back", "public_inventory", "Notify when back",
                requires_modules=("notifications",)),
        feature("stocktake.discipline", "stocktake", "Stocktake discipline"),
        feature("machines.public_detail", "machines", "Public machine details"),
        feature("machines.material_catalogue", "machines", "Local material catalogue"),
        feature("machines.structured_intake", "machine_service", "Structured machine intake",
                requires_modules=("machines",)),
        # Parented to `machines` since #97 folded the `maintenance` module key; keys unchanged.
        feature("maintenance.meters", "machines", "Usage-based maintenance",
                requires_features=("machines.maintenance",)),
        feature("maintenance.calendar_feed", "machines", "Maintenance calendar feed",
                requires_features=("machines.maintenance",)),
    )

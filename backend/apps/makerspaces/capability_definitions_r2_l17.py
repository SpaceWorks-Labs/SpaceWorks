"""Release-2 lane L17: maintenance, To-Buy, warranty and repairs under EACH parent.

Owner decisions #97 and #128 C-9. The `maintenance` and `procurement` module keys are
retired; what they switched is now a two-level capability under the parent it serves,
each with its own switch:

* machine ones under `machines`, room ones under `bookings`;
* item ones under the parentless inventory family (`parent_module=None`, exactly like
  `inventory.kiosk` and `inventory.self_checkout`), which the console labels "Inventory".

Rooms get no To-Buy or warranty switch in release 2 (#137 Q-C3). The Django apps stay
internal and separable: `app_label` names the app each switch gates, so a tombstoned app
reads as off whatever the stored switch says.

Repairs, issue reporting and the inventory/room maintenance schedules are RESERVED here
for L12/L16, which build their surfaces. Until then they have nothing to switch, so they
stay out of the frontend (`frontend_exposed=False`) and are reachable only in /control/.
"""

RESERVED = "Reserved for release 2 repairs and issue reporting; no effect yet."
# Switches with no surface yet: install bundles and profiles never tick them.
RESERVED_KEYS = frozenset({
    "machines.repairs", "machines.issue_reporting", "inventory.maintenance",
    "inventory.repairs", "inventory.issue_reporting", "bookings.room_maintenance",
    "bookings.room_repairs", "bookings.issue_reporting",
})
# What the retired module keys used to switch, per profile that installed them.
FOLDED_KEYS = ("machines.maintenance", "machines.tobuy", "machines.warranty",
               "inventory.tobuy", "inventory.warranty")


def definitions(feature):
    return (
        feature(
            "machines.maintenance", "machines", "Machine maintenance",
            "Maintenance schedules, work orders, usage meters and reminders for machines.",
            app_label="maintenance",
        ),
        feature(
            "machines.tobuy", "machines", "Machine To-Buy",
            "To-Buy rows for machine consumables such as filament pools, including the "
            "automatic low-stock drafts.",
            app_label="procurement",
        ),
        feature(
            "machines.warranty", "machines", "Machine warranty",
            "Warranty records and documents on machines.",
            app_label="warranty",
        ),
        feature("machines.repairs", "machines", "Machine repairs & technicians", RESERVED,
                frontend_exposed=False),
        feature("machines.issue_reporting", "machines", "Machine issue reporting", RESERVED,
                frontend_exposed=False),
        feature(
            "inventory.maintenance", None, "Inventory maintenance",
            "Maintenance schedules on inventory products and assets. " + RESERVED,
            frontend_exposed=False, app_label="maintenance",
        ),
        feature(
            "inventory.tobuy", None, "Inventory To-Buy",
            "To-Buy rows for inventory items, reorder drafts and (later) the shop.",
            app_label="procurement",
        ),
        feature(
            "inventory.warranty", None, "Inventory warranty",
            "Warranty records and documents on inventory assets.",
            app_label="warranty",
        ),
        feature("inventory.repairs", None, "Inventory repairs & technicians", RESERVED,
                frontend_exposed=False),
        feature("inventory.issue_reporting", None, "Inventory issue reporting", RESERVED,
                frontend_exposed=False),
        feature(
            "bookings.room_maintenance", "bookings", "Room maintenance",
            "Maintenance schedules on bookable spaces. " + RESERVED,
            frontend_exposed=False, app_label="maintenance",
        ),
        feature("bookings.room_repairs", "bookings", "Room repairs", RESERVED,
                frontend_exposed=False),
        feature("bookings.issue_reporting", "bookings", "Room issue reporting", RESERVED,
                frontend_exposed=False),
    )

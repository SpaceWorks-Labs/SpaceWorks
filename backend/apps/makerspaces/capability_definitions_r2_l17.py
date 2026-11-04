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

Repairs, issue reporting and the inventory/room maintenance schedules were reserved here
and are built by lane L16 (the `maintenance.repairs` package): each `*.repairs` switch
needs its parent's maintenance switch, because a repair job is L12's work order, which
lives under maintenance; reporting works on its own (notify only, #93).
"""

# L16 consumed every reserved switch; nothing here is surface-less any more.
RESERVED_KEYS = frozenset()
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
        feature("machines.repairs", "machines", "Machine repairs & technicians",
                "Repair jobs on machines: triage reported issues, send them to technicians by email or "
                "chat, log visits, parts and quotes, and record payouts in the finance ledger.",
                requires_features=("machines.maintenance",), app_label="maintenance"),
        feature("machines.issue_reporting", "machines", "Machine issue reporting",
                "Members report a problem from their own machine job; the Machine Manager and the "
                "Space Manager are notified.", app_label="maintenance"),
        feature(
            "inventory.maintenance", None, "Inventory maintenance",
            "Maintenance schedules and logs on inventory items and units, and their work orders.",
            app_label="maintenance",
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
        feature("inventory.repairs", None, "Inventory repairs & technicians",
                "Repair jobs on items and units: triage, technicians, parts, quotes and payouts.",
                requires_features=("inventory.maintenance",), app_label="maintenance"),
        feature("inventory.issue_reporting", None, "Inventory issue reporting",
                "Borrowers report a problem with an item from their own loan (account-less borrowers by "
                "their verified email); the Inventory Manager and the Space Manager are notified.",
                app_label="maintenance"),
        feature(
            "bookings.room_maintenance", "bookings", "Room maintenance",
            "Maintenance schedules and logs on bookable rooms, and their work orders.",
            app_label="maintenance",
        ),
        feature("bookings.room_repairs", "bookings", "Room repairs",
                "Repair jobs on rooms: technicians, quotes and payouts, and taking a room out of "
                "service (block or warn new bookings).",
                requires_features=("bookings.room_maintenance",), app_label="maintenance"),
        feature("bookings.issue_reporting", "bookings", "Room issue reporting",
                "Bookers report a problem from their own booking; the Booking Manager and the Space "
                "Manager are notified.", app_label="maintenance"),
    )

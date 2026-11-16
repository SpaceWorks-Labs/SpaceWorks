"""Release-2 GAP2 M2: due and overdue reminders for item and room maintenance.

L16 put item and room maintenance under their parents (#128 C-9) with due and overdue
shown in the list only. These two keys add the reminder job beside the machine one
(`maintenance.reminders`), each switchable per space. They are ON by default, so a space
that turns its item or room maintenance on gets reminders unless it opts out; they need the
parent's maintenance switch and the notifications module. Off: no reminder is queued and a
queued one is dropped at send time; schedules and logs are untouched.
"""


def definitions(feature):
    return (
        feature("inventory.maintenance_reminders", None, "Item maintenance reminders",
                "Tell the Inventory Manager when item and unit maintenance is due and when it is overdue.",
                default_enabled=True, requires_modules=("notifications",),
                requires_features=("inventory.maintenance",), app_label="maintenance"),
        feature("bookings.room_maintenance_reminders", "bookings", "Room maintenance reminders",
                "Tell the Booking Manager when room maintenance is due and when it is overdue.",
                default_enabled=True, requires_modules=("notifications",),
                requires_features=("bookings.room_maintenance",), app_label="maintenance"),
    )

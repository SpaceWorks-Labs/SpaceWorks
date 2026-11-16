"""Live source switches for channel report dimensions (decision 218).

Mixed apps such as accounts, admin_api and the core payment ledger remain readable.
Unambiguous optional areas and flow completions disappear while their source is off;
the stored counters are retained so re-enabling the source restores its history.
"""

from apps.operations.report_sources import source_enabled

AREA_SOURCES = {
    "events": "events", "event_reimbursements": "event_reimbursements",
    "bookings": "bookings", "machines": "machines", "devices": "devices",
    "analytics": "analytics", "notifications": "notifications", "shop": "shop",
    "hardware_requests": "loans.enabled", "inventory": "public_inventory",
    "payments_rail": "payments",
    "presence": "presence", "id_programmes": "membership.id_programmes",
    "card_designs": "membership|events|bookings",
    "procurement": "inventory.tobuy|machines.tobuy",
    "warranty": "inventory.warranty|machines.warranty",
    "maintenance": "inventory.maintenance|machines.maintenance|bookings.room_maintenance|"
                   "inventory.issue_reporting|machines.issue_reporting|bookings.issue_reporting|safety.incidents",
}
FLOW_SOURCES = {
    "request_submitted": "loans.enabled", "item_issued": "loans.enabled",
    "item_returned": "loans.enabled", "booking_made": "bookings",
    "event_registered": "events", "machine_job_requested": "machine_service",
    "payment_started": "payments",
}


def visible_area(space, area):
    source = FLOW_SOURCES.get(area[5:]) if area.startswith("flow:") else AREA_SOURCES.get(area)
    return source is None or source_enabled(space, source)

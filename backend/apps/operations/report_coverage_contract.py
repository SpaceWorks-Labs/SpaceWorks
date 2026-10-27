"""Phase 1f v2 C1 acceptance table (coverage associations, NOT module gates).

Grouped plan rows associate the area's keys with its modules. Builders still use
required_modules for actual source prerequisites and section_modules for optional
sections; never require every module in an area to run every report. Presence,
audit, organizations and platform are coverage areas, not new installable keys.
"""

_ROWS = (
    (("public_inventory", "request_workflow", "staff_admin", "guest_handover", "asset_units"),
     ("most-lent", "asset-usage", "loan-throughput", "inventory-utilisation", "overdue-loans",
      "damaged-lost", "longest-loans", "request-funnel", "problem-reports", "summary")),
    (("scanner", "qr_management", "qr_print_batches", "containers"), ("qr-scans", "inventory-control")),
    (("evidence_uploads",), ("evidence-compliance",)),
    (("bulk_import",), ("import-quality",)),
    (("stocktake", "stock_transfers", "procurement"),
     ("stocktake-variance", "stock-transfers", "procurement-performance", "stock-health", "inventory-watch-demand")),
    (("machines", "machine_service", "printing", "maintenance"),
     ("machine-usage", "machine-usage-members", "machine-usage-heatmap", "machine-downtime",
      "maintenance-activity", "machine-service", "service-queue-times", "printer-jobs",
      "machine-errors", "consumable-usage", "consumable-pools", "warranty-expiry")),
    (("bookings",), ("booking-utilization", "booking-occupancy", "booking-lead-time", "booking-top-members")),
    (("events",), ("event-signups", "event-revenue", "event-funnel", "event-checkin-times", "event-feedback-scores")),
    (("membership", "member_accounts"), ("membership-growth", "member-retention", "membership-revenue")),
    (("payments",), ("revenue-over-time", "payments-ageing", "payment-reconciliation", "cash-book")),
    (("notifications", "email", "telegram", "slack", "mattermost", "discord", "webhook"),
     ("communications-health",)),
    (("mobile",), ("mobile-devices", "mobile-auth")),
    (("devices",), ("device-health",)),
    (("reports", "sms", "whatsapp"), ("module-operational-health",)),
    (("presence",), ("presence-activity",)),
    (("audit",), ("audit-activity",)),
    (("organizations",), ("organization-membership",)),
    (("platform",), ("platform-services", "platform-usage")),
    (("sms", "whatsapp"), ("communications-health", "platform-services")),
)

REPORT_COVERAGE_CONTRACT = {module: keys for modules, keys in _ROWS for module in modules}
# These areas have no installable module key. They may have coverage declarations
# in REPORT_MODULE_COVERAGE, but must never become required_modules/section_modules.
REPORT_COVERAGE_AREAS = frozenset({"presence", "audit", "organizations", "platform"})


def required_report_modules():
    """Invert the table for one independently actionable acceptance test per key."""
    result = {}
    for module, keys in REPORT_COVERAGE_CONTRACT.items():
        for key in keys:
            result.setdefault(key, set()).add(module)
    return result

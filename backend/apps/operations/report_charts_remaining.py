"""F1 charts for legacy reports and tenant-local detail projections.

Loan rows expose count=1; other detail projections retain their table contracts.
Money values use currency partitions; printer/health charts use non-money units
because those older report shapes do not declare a currency.
"""

from .reports_de_common import chart


def table(field):
    """An F1 table has a row dimension and no numeric measures to aggregate."""
    return {"series": [], "x": {"field": field, "kind": "category"}, "values": [],
            "currency_field": None, "partition": None, "negatives": "clip",
            "truncation": None, "alt_template": "{count} detail rows"}


LEGACY_CHARTS = {
    "taken-items": chart("product", (("issued_quantity", "units"),), top=10),
    "active-loans": chart("issued_at", (("count", "loans"),), series=("status",), time=True, tenant=False),
    "returns": chart("closed_at", (("count", "loans"),), series=("status",), time=True, tenant=False),
    "damaged-missing": chart("product", (("damaged_quantity", "units"), ("missing_quantity", "units")), top=10),
    "recently-added": chart("created_at", (("total_quantity", "units"),), time=True),
    "top-borrowers": chart("holder", (("requests", "loans"), ("items_borrowed", "units")), tenant=False, top=10),
}

PAYMENT_CASH_CHART = chart("method", tuple((field, "currency_major") for field in (
    "collected_amount", "refunded_amount", "net_amount")), series=("makerspace_id",), currency=True, negatives=True)
ATTENDANCE_CHART = chart("starts_at", (("registrations", "registrations"), ("attended", "attendees")),
                         series=("event_id", "title"), time=True)
MEMBER_ACTIVITY_CHART = chart("makerspace_name", tuple((field, "memberships") for field in (
    "new_members", "active_members", "revoked_members", "verified_members")))
PRINTER_SERVICE_CHART = chart("machine_name", tuple((field, "hours") for field in (
    "completed_hours", "failed_partial_hours", "manual_hours")), series=("machine_id", "model"), top=10)
HEALTH_CHART = chart("makerspace_id", (("events_completed_attendance_rate_percent", "percent"),
                                         ("bookings_reservation_utilization_percent", "percent")))
EVIDENCE_CHART = chart("period", tuple((field, "photos") for field in (
    "created_count", "attached_count", "unattached_count")), series=("evidence_type",), time=True)
IMPORT_CHART = chart("period", tuple((field, "rows") for field in (
    "created_rows", "updated_rows", "error_rows", "warning_rows")), series=("mode", "status"), time=True)
COMMUNITY_CHART = chart("period", (("activations", "accounts"), ("revocations", "accounts")),
                        series=("module_key",), time=True)
CERTIFICATION_CHART = chart("machine_type", (("certified_members", "members"), ("active_members", "members")),
                            series=("certification_type",), top=10)

# Keep effective/correction and refund-status dimensions separate: a superseded
# receipt or failed refund is ledger history, not collected or refunded money.
LEDGER_CHART = chart("date", tuple((field, "currency_major") for field in (
    "collected_amount", "owed_amount", "refunded_amount")), time=True, currency=True, negatives=True,
    series=("row_kind", "effective", "refund_status"), tenant=False)
JOURNAL_CHART = chart("account_code", (("debit", "currency_major"), ("credit", "currency_major")),
                      currency=True, negatives=True, tenant=False)

REGISTRATIONS_CHART = table("registration_id")
FEEDBACK_CHART = table("response_id")
ATTENDANCE_PDF_CHART = {**ATTENDANCE_CHART, "partition": None}
RESOURCE_UTILIZATION_CHART = chart("space_name", tuple((field, "reservations") for field in (
    "booked", "completed", "no_show", "cancelled")), tenant=False)
RESERVATIONS_CHART = table("booking_id")
AUDIT_CHART = table("created_at")

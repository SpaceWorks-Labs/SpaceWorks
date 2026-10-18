"""Area C registration, including its public schemas and organization math."""

from apps.accounts import rbac
from .org_report_aggregate import register_combine
from .org_machine_reports import COMBINERS
from .report_types import ReportDefinition
from .reports_machine_common import GRAINS
from .reports_machine_downtime import FIELDS as DOWNTIME_FIELDS
from .reports_machine_health import ERROR_FIELDS, PRINTER_FIELDS, WARRANTY_FIELDS
from .reports_machine_heatmap import FIELDS as HEATMAP_FIELDS
from .reports_machine_maintenance_v2 import FIELDS as MAINTENANCE_FIELDS
from .reports_machine_queue import FIELDS as QUEUE_FIELDS
from .reports_machine_service_v2 import FIELDS as SERVICE_FIELDS
from .reports_machine_usage_v2 import FIELDS as USAGE_FIELDS, MEMBER_FIELDS


def _chart(x, values, series, *, time=True, top=False, tenant=True, negatives="clip"):
    return {
        "series": list(series), "x": {"field": x, "kind": "time" if time else "category"},
        "values": [{"field": field, "unit": unit} for field, unit in values],
        "currency_field": None, "partition": "tenant" if tenant else None, "negatives": negatives,
        "truncation": {"top_n": 5, "other_label": "Other"} if top else None,
        "alt_template": "{count} observations",
    }


def _definition(key, builder, fields, modules, hint, chart, **kwargs):
    return ReportDefinition(
        key, f"apps.operations.{builder}", fields, modules,
        required_action=rbac.Action.MANAGE_MACHINES, title=key.replace("-", " ").title(),
        chart_hint=hint, chart_spec=chart, **kwargs,
    )


MACHINE_REPORT_DEFINITIONS = (
    _definition("machine-usage", "reports_machine_usage_v2.build_machine_usage", USAGE_FIELDS, ("machines",), "multi_line",
                _chart("period", (("service_hours", "hours"), ("manual_hours", "hours"), ("booked_hours", "hours")), ("measure", "machine_name", "machine_type_id"), top=True),
                section_modules=("machine_service", "bookings"), version=2, grains=GRAINS),
    _definition("machine-usage-members", "reports_machine_usage_v2.build_machine_usage_members", MEMBER_FIELDS, ("machines",), "bar",
                _chart("member_id", (("hours", "hours"),), ("measure", "period", "machine_type_id"), time=False, tenant=False),
                section_modules=("machine_service", "bookings"), grains=GRAINS, identity_bearing=True,
                deployment_aggregate=False, schedulable=False),
    _definition("machine-usage-heatmap", "reports_machine_heatmap.build_machine_usage_heatmap", HEATMAP_FIELDS, ("machines",), "heatmap",
                _chart("hour", (("service_hours", "hours"), ("manual_hours", "hours"), ("booked_hours", "hours")), ("weekday", "measure", "period", "machine_type_id"), time=False),
                section_modules=("machine_service", "bookings"), grains=GRAINS),
    _definition("machine-downtime", "reports_machine_downtime.build_machine_downtime", DOWNTIME_FIELDS, ("machines",), "stacked_bar",
                _chart("period", (("status_hours", "hours"),), ("machine_id", "status")), grains=GRAINS),
    _definition("maintenance-activity", "reports_machine_maintenance_v2.build_maintenance_activity", MAINTENANCE_FIELDS,
                ("machines", "maintenance"), "line", _chart("period", (("log_count", "maintenance logs"),), ("machine_id",)), version=2, grains=GRAINS),
    _definition("machine-service", "reports_machine_service_v2.build_machine_service", SERVICE_FIELDS, ("machines", "machine_service"), "line",
                _chart("period", (("failure_rate", "percent"),), ("machine_id",)), version=2, grains=GRAINS),
    _definition("service-queue-times", "reports_machine_queue.build_service_queue_times", QUEUE_FIELDS, ("machines", "machine_service"), "line",
                _chart("period", (("median_minutes", "minutes"), ("p90_minutes", "minutes"), ("p95_minutes", "minutes")), ("queue_id", "bucket_id", "stage")), grains=GRAINS),
    _definition("printer-jobs", "reports_machine_health.build_printer_jobs", PRINTER_FIELDS, ("machines", "printing", "devices"), "stacked_bar",
                _chart("period", (("job_count", "jobs"),), ("machine_id", "state", "outcome")), grains=GRAINS),
    _definition("machine-errors", "reports_machine_health.build_machine_errors", ERROR_FIELDS, ("machines",), "stacked_bar",
                _chart("period", (("error_count", "errors"),), ("machine_id", "severity")), grains=GRAINS),
    _definition("warranty-expiry", "reports_machine_health.build_warranty_expiry", WARRANTY_FIELDS, ("machines",), "table",
                _chart("machine_name", (("days_until_expiry", "days"),), ("machine_id",), time=False, negatives="allow")),
)
MACHINE_REPORT_KEYS = frozenset(d.key for d in MACHINE_REPORT_DEFINITIONS)

for _key, _combine in COMBINERS.items():
    register_combine(_key, _combine)

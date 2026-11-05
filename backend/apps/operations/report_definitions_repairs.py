"""RP-5: the repairs and technician report family (L16 follow-up).

One family serves every area that runs repairs: the Technician (`work_repairs`) and the
Machine, Inventory and Booking Managers (`alternate_actions`). Each builder narrows its
rows to the viewer through the repairs authority, so these reports are tenant-local:
never scheduled (a scheduled copy has no viewer to narrow for), never deployment-wide,
and excluded from organization dashboards. The workload report names people, so it is
identity-bearing (a superadmin reads it inside a PII window).
"""

from apps.accounts import rbac
from apps.maintenance.repairs.report_fields import PARTS_FIELDS, REPAIR_TIME_FIELDS, WORK_ORDER_FIELDS, WORKLOAD_FIELDS
from apps.operations.report_charts_remaining import table
from apps.operations.report_types import ReportDefinition
from apps.operations.reports_de_common import chart

_BUILDERS = "apps.maintenance.repairs.reports."
REPAIRS_SOURCE = "machines.repairs|inventory.repairs|bookings.room_repairs"
WORK_ORDER_SOURCE = REPAIRS_SOURCE + "|machines.maintenance|inventory.maintenance|bookings.room_maintenance"
MANAGERS = (rbac.Action.MANAGE_MACHINES, rbac.Action.EDIT_INVENTORY, rbac.Action.MANAGE_BOOKINGS)


def _repairs(key, builder, fields, title, source, chart_spec, chart_hint, **extra):
    return ReportDefinition(key, _BUILDERS + builder, fields, (source,), required_action=rbac.Action.WORK_REPAIRS,
                            alternate_actions=MANAGERS, title=title, deployment_aggregate=False,
                            schedulable=False, chart_spec=chart_spec, chart_hint=chart_hint, **extra)


REPAIRS_REPORT_DEFINITIONS = (
    _repairs("repairs-work-orders", "build_work_orders", WORK_ORDER_FIELDS, "Open and overdue work orders",
             WORK_ORDER_SOURCE, table("work_order_id"), "table"),
    _repairs("repairs-technician-workload", "build_technician_workload", WORKLOAD_FIELDS, "Technician workload",
             REPAIRS_SOURCE, chart("technician", (("open_jobs", "jobs"), ("fixed_in_period", "jobs")),
                                   series=("technician_kind",), tenant=False, top=10),
             "grouped_bar", identity_bearing=True),
    _repairs("repairs-time-by-area", "build_repair_time", REPAIR_TIME_FIELDS, "Repair time per area",
             REPAIRS_SOURCE, chart("area", (("average_hours_to_fix", "hours"), ("median_hours_to_fix", "hours")),
                                   series=("machine_type",), tenant=False),
             "grouped_bar"),
    _repairs("repairs-parts-used", "build_parts_used", PARTS_FIELDS, "Repair parts used and needed",
             REPAIRS_SOURCE, chart("part", (("quantity", "units"),), series=("kind",), tenant=False, top=10),
             "grouped_bar"),
)
REPAIRS_REPORT_KEYS = frozenset(definition.key for definition in REPAIRS_REPORT_DEFINITIONS)
#: Builders that narrow rows to the viewer, so the runner passes `actor`.
REPAIRS_ACTOR_REPORT_KEYS = REPAIRS_REPORT_KEYS

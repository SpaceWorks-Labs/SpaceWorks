"""Tenant-local operational counts, using the existing report registry."""
from django.utils.translation import gettext_noop

from apps.accounts import rbac
from .report_types import ReportDefinition
from .reports_de_common import chart
from .report_charts_remaining import table
from .reports_loan_context import FIELDS as PURPOSE_FIELDS
from .reports_loan_context_details import FIELDS as EQUIPMENT_FIELDS
from .reports_loan_timeline import FIELDS as TIMELINE_FIELDS

CONSUMABLE_CONTEXT_FIELDS = (
    "product_id", "product_name", "planned_quantity", "used_quantity", "remaining_planned",
    "available_quantity", "shortage_quantity", "reorder_point", "replenishment_quantity",
    "currency", "unit_cost", "estimated_cost",
)
LOAN_CONTEXT_REPORT_KEYS = frozenset({
    "loan-purpose-summary", "event-equipment", "booking-equipment",
    "event-consumables", "booking-consumables",
    "event-loan-timeline", "booking-loan-timeline",
})
LOAN_CONTEXT_REPORT_DEFINITIONS = (
    ReportDefinition(
        "loan-purpose-summary",
        "apps.operations.reports_loan_context.build_loan_purpose_summary",
        PURPOSE_FIELDS,
        ("request_workflow",),
        required_action=rbac.Action.VIEW_INVENTORY,
        title=gettext_noop("Equipment loans by purpose"),
        # v2 (decision 216 item 16): units, overdue, loan hours and loss cost per purpose.
        version=2,
        schedulable=False,
        deployment_aggregate=False,
        chart_hint="stacked_bar",
        chart_spec=chart("context", (("count", "loans"),), series=("status", "currency"), tenant=False),
    ),
    ReportDefinition(
        "event-equipment",
        "apps.operations.reports_loan_context_details.build_event_equipment",
        EQUIPMENT_FIELDS,
        ("request_workflow", "events"),
        required_action=rbac.Action.VIEW_INVENTORY,
        version=2,
        title=gettext_noop("Equipment loans for an event"),
        subject_kind="event",
        identity_bearing=True,
        schedulable=False,
        deployment_aggregate=False,
        chart_hint="table",
        chart_spec=table("request_id"),
    ),
    ReportDefinition(
        "booking-equipment",
        "apps.operations.reports_loan_context_details.build_booking_equipment",
        EQUIPMENT_FIELDS,
        ("request_workflow", "bookings"),
        required_action=rbac.Action.VIEW_INVENTORY,
        version=2,
        title=gettext_noop("Equipment loans for a booking"),
        subject_kind="booking",
        identity_bearing=True,
        schedulable=False,
        deployment_aggregate=False,
        chart_hint="table",
        chart_spec=table("request_id"),
    ),
    # Owner decision 216 item 16: one subject's linked-loan lifecycle, oldest first.
    *(ReportDefinition(
        f"{kind}-loan-timeline",
        f"apps.operations.reports_loan_timeline.build_{kind}_loan_timeline",
        TIMELINE_FIELDS,
        ("request_workflow", module),
        required_action=rbac.Action.VIEW_INVENTORY,
        title=title,
        subject_kind=kind,
        identity_bearing=True,
        schedulable=False,
        deployment_aggregate=False,
        chart_hint="table",
        chart_spec=table("request_id"),
    ) for kind, module, title in (
        ("event", "events", gettext_noop("Equipment loan timeline for an event")),
        ("booking", "bookings", gettext_noop("Equipment loan timeline for a booking")),
    )),
    # Owner decision 216 item 6: activity-attributed consumable use, read-only.
    *(ReportDefinition(
        f"{kind}-consumables",
        f"apps.operations.reports_consumable_context.build_{kind}_consumables",
        CONSUMABLE_CONTEXT_FIELDS,
        ("inventory.consumables", module),
        required_action=rbac.Action.VIEW_INVENTORY,
        title=title,
        subject_kind=kind,
        schedulable=False,
        deployment_aggregate=False,
        chart_hint="table",
        chart_spec=table("product_name"),
    ) for kind, module, title in (
        ("event", "events", gettext_noop("Consumables used for an event")),
        ("booking", "bookings", gettext_noop("Consumables used for a booking")),
    )),
)

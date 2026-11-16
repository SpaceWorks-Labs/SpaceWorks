"""Decision 342 report definitions: machine use logged with an event.

Behind the machines and events modules, MANAGE_MACHINES narrowed by machine scope (they ride the machine
report family so the actor is forwarded). Tenant-local: never added into organisation totals. The per-event
rows name people, so that report is identity-bearing and unschedulable.
"""
from django.utils.translation import gettext_noop

from apps.accounts import rbac
from apps.operations.report_charts_remaining import table
from apps.operations.report_types import ReportDefinition
from apps.operations.reports_machine_event import EVENT_FIELDS, USE_FIELDS

_BUILDERS = "apps.operations.reports_machine_event."

MACHINE_EVENT_REPORT_DEFINITIONS = (
    ReportDefinition(
        "machine-use-by-event", _BUILDERS + "build_machine_use_by_event", EVENT_FIELDS, ("machines", "events"),
        required_action=rbac.Action.MANAGE_MACHINES, title=gettext_noop("Machine use by event"),
        deployment_aggregate=False, chart_hint="table", chart_spec=table("event_title"),
    ),
    ReportDefinition(
        "event-machine-use", _BUILDERS + "build_event_machine_use", USE_FIELDS, ("machines", "events"),
        required_action=rbac.Action.MANAGE_MACHINES, title=gettext_noop("Machine use for an event"),
        subject_kind="event", identity_bearing=True, schedulable=False, deployment_aggregate=False,
        chart_hint="table", chart_spec=table("title"),
    ),
)
MACHINE_EVENT_REPORT_KEYS = frozenset(definition.key for definition in MACHINE_EVENT_REPORT_DEFINITIONS)

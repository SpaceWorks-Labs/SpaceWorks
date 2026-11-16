"""Lane L23 machine-session report definitions (#158.6).

Behind `reports` (the report surfaces) and the `machines.sessions` capability through
`required_feature`; MANAGE_MACHINES narrowed by machine scope (they ride the machine
report family, so the actor is forwarded). All tenant-local (`deployment_aggregate=False`)
and excluded from organisation totals; the two person lists are identity-bearing
(unschedulable, VIEW_AUDIT for member names, a superadmin needs an open PII window).
"""

from apps.accounts import rbac
from apps.operations.report_charts_remaining import table
from apps.operations.report_types import ReportDefinition
from apps.operations.reports_machine_sessions import (
    BUSIEST_FIELDS, FLAGGED_FIELDS, IDLE_FIELDS, SESSION_FIELDS, UTILISATION_FIELDS,
)

_BUILDERS = "apps.operations.reports_machine_sessions."
FEATURE = "machines.sessions"


def _chart(x, values, series, *, time=False):
    return {"series": list(series), "x": {"field": x, "kind": "time" if time else "category"},
            "values": [{"field": field, "unit": unit} for field, unit in values], "currency_field": None,
            "partition": None, "negatives": "clip", "truncation": None, "alt_template": "{count} observations"}


def _session_report(key, builder, fields, title, *, identity=False, chart=None, hint="table"):
    return ReportDefinition(
        key, _BUILDERS + builder, fields, ("machines",), required_action=rbac.Action.MANAGE_MACHINES, title=title,
        required_feature=FEATURE, deployment_aggregate=False, identity_bearing=identity, schedulable=not identity,
        chart_hint=hint, chart_spec=chart or table(fields[0]),
    )


SESSION_REPORT_DEFINITIONS = (
    _session_report("machine-sessions", "build_machine_sessions", SESSION_FIELDS,
                    "Machine sessions by member, machine and type", identity=True),
    _session_report("machine-session-utilisation", "build_machine_session_utilisation", UTILISATION_FIELDS,
                    "Machine utilisation (busy hours over open hours)", hint="bar",
                    chart=_chart("machine_type", (("utilisation_percent", "percent"),), ("level",))),
    _session_report("machine-session-busiest", "build_machine_session_busiest", BUSIEST_FIELDS,
                    "Busiest days and hours", hint="heatmap",
                    chart=_chart("hour", (("busy_hours", "hours"),), ("weekday",))),
    _session_report("machine-session-idle", "build_machine_session_idle", IDLE_FIELDS, "Idle machines"),
    _session_report("machine-session-flagged", "build_machine_session_flagged", FLAGGED_FIELDS,
                    "Flagged and auto-stopped sessions", identity=True),
)
SESSION_REPORT_KEYS = frozenset(definition.key for definition in SESSION_REPORT_DEFINITIONS)

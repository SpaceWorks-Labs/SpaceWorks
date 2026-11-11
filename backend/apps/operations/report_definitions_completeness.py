"""Decision 248: the area reports and exports the role completeness audit found missing.

Every report is per space (`deployment_aggregate=False`), never scheduled (a scheduled copy has no viewer to
narrow for) and excluded from organization totals. Each is keyed to its own AREA action (decision 224(a)), never
to `view_audit`; the three that narrow rows to the viewer's reach read the actor. Inventory reports use the
"Inventory" name (decision 247). The five people exports are identity-bearing: a superadmin reads them only
inside an open PII window.
"""

from django.utils.translation import gettext_noop

from apps.accounts import rbac
from apps.operations.report_charts_remaining import table
from apps.operations.report_types import ReportDefinition
from apps.operations import (
    reports_completeness_inventory as inventory, reports_completeness_ops as ops,
    reports_completeness_people as people,
)

A = rbac.Action
_PATH = "apps.operations."


def _report(key, module, builder, fields, title, modules, action, *, identity=False, alternates=(), sections=()):
    return ReportDefinition(
        key, f"{_PATH}{module}.{builder}", fields, modules, required_action=action, alternate_actions=alternates,
        title=title, section_modules=sections, deployment_aggregate=False, schedulable=False, identity_bearing=identity,
        chart_hint="table", chart_spec=table(fields[0]),
    )


COMPLETENESS_REPORT_DEFINITIONS = (
    _report("inventory-valuation", "reports_completeness_inventory", "build_inventory_valuation",
            inventory.VALUATION_FIELDS, gettext_noop("Inventory valuation"), ("public_inventory",), A.EDIT_INVENTORY,
            sections=("public_inventory",)),
    _report("inventory-utilisation-by-category", "reports_completeness_inventory",
            "build_inventory_utilisation_by_category", inventory.UTILISATION_FIELDS,
            gettext_noop("Inventory utilisation by category"), ("public_inventory",), A.VIEW_INVENTORY,
            sections=("public_inventory",)),
    _report("overdue-by-borrower", "reports_completeness_inventory", "build_overdue_by_borrower",
            inventory.OVERDUE_BORROWER_FIELDS, gettext_noop("Overdue inventory by borrower"), ("request_workflow",),
            A.VIEW_INVENTORY, identity=True),
    _report("incidents-register", "reports_completeness_ops", "build_incidents_register", ops.INCIDENT_FIELDS,
            gettext_noop("Incidents register"), ("safety.incidents",), A.MANAGE_MAKERSPACE, identity=True,
            alternates=(A.MANAGE_MACHINES, A.EDIT_INVENTORY, A.MANAGE_EVENTS, A.MANAGE_BOOKINGS, A.WORK_REPAIRS,
                        A.RUN_MAINTENANCE)),
    _report("machine-jobs", "reports_completeness_ops", "build_machine_jobs", ops.JOB_FIELDS,
            gettext_noop("Machine jobs register"), ("machines", "machine_service"), A.MANAGE_MACHINES),
    _report("certification-holders", "reports_completeness_ops", "build_certification_holders", ops.HOLDER_FIELDS,
            gettext_noop("Certification holders"), ("machines",), A.MANAGE_MACHINES, identity=True),
    _report("roster-export", "reports_completeness_people", "build_roster_export", people.ROSTER_FIELDS,
            gettext_noop("Member roster"), ("membership",), A.MANAGE_MEMBERS, identity=True),
    _report("guest-passes-export", "reports_completeness_people", "build_guest_passes_export",
            people.GUEST_PASS_FIELDS, gettext_noop("Guest passes"), ("membership", "membership.guest_passes"), A.MANAGE_MEMBERS,
            identity=True),
    _report("volunteer-hours-export", "reports_completeness_people", "build_volunteer_hours_export",
            people.VOLUNTEER_FIELDS, gettext_noop("Volunteer hours"), ("membership", "membership.volunteer_credit"),
            A.MANAGE_MEMBERS, identity=True),
    _report("minors-consent-export", "reports_completeness_people", "build_minors_consent_export",
            people.MINOR_FIELDS, gettext_noop("Minors and guardian consent"), ("membership", "membership.minors"),
            A.MANAGE_MEMBERS, identity=True),
    _report("staff-roster-export", "reports_completeness_people", "build_staff_roster_export", people.STAFF_FIELDS,
            gettext_noop("Staff roster"), (), A.MANAGE_MAKERSPACE, identity=True),
)
COMPLETENESS_REPORT_KEYS = frozenset(definition.key for definition in COMPLETENESS_REPORT_DEFINITIONS)
#: Builders that narrow rows to the viewer, so the runner passes `actor`.
COMPLETENESS_ACTOR_REPORT_KEYS = frozenset({"incidents-register", "machine-jobs", "certification-holders"})

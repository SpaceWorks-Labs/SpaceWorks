"""Decision 341 report definition: consumables per machine type, by the type's profile.

Behind `machines` + `machine_service`, MANAGE_MACHINES narrowed by machine scope (it rides the machine
report family, so the actor is forwarded). Counts and quantities only, no person. Tenant-local: a profile
key means what ONE space defined, so it is never summed across an organisation.
"""
from django.utils.translation import gettext_noop

from apps.accounts import rbac
from apps.operations.report_charts_remaining import table
from apps.operations.report_types import ReportDefinition
from apps.operations.reports_machine_consumables import FIELDS

MACHINE_CONSUMABLE_REPORT_DEFINITIONS = (
    ReportDefinition(
        "machine-consumables", "apps.operations.reports_machine_consumables.build_machine_consumables", FIELDS,
        ("machines", "machine_service"), required_action=rbac.Action.MANAGE_MACHINES,
        title=gettext_noop("Consumables by machine type"), deployment_aggregate=False,
        chart_hint="table", chart_spec=table("machine_type"),
    ),
)
MACHINE_CONSUMABLE_REPORT_KEYS = frozenset(definition.key for definition in MACHINE_CONSUMABLE_REPORT_DEFINITIONS)

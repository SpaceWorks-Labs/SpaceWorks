"""Release-2 L3: the member-card issuance tile (X27). Tenant-local, counts only."""
from django.utils.translation import gettext_noop
from apps.accounts import rbac
from apps.operations.report_charts_remaining import table
from apps.operations.report_types import ReportDefinition
from apps.operations.reports_cards import FIELDS

CARD_REPORT_DEFINITIONS = (
    ReportDefinition("member-card-issuance", "apps.operations.reports_cards.build_card_issuance", FIELDS,
                     ("membership",), required_action=rbac.Action.SCAN_MEMBER_CARDS, title=gettext_noop("Member card issuance"),
                     deployment_aggregate=False, chart_hint="table", chart_spec={**table("metric"), "partition": None}),
)
CARD_REPORT_KEYS = frozenset(definition.key for definition in CARD_REPORT_DEFINITIONS)

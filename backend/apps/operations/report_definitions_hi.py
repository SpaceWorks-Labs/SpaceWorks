"""H/I report registration, chart contract and explicit organization combination."""

from django.utils.translation import gettext_noop
from functools import partial

from apps.accounts import rbac
from .org_report_aggregate import register_combine
from .report_types import ReportDefinition
from .reports_hi_common import combine_counts
from .org_reports_messaging import combine_communications
from .report_fields_hi import (
    COMMUNICATION_FIELDS, MESSAGING_STATUS_COUNTS,
    MOBILE_AUTH_FIELDS, MOBILE_AUTH_GROUPS, MOBILE_DEVICE_FIELDS, MOBILE_DEVICE_GROUPS,
)


def _chart(series, values, alt):
    return {
        "series": series, "x": {"field": "period", "kind": "time"},
        "values": [{"field": field, "unit": unit} for field, unit in values],
        "currency_field": None, "partition": "tenant", "negatives": "clip",
        "truncation": None, "alt_template": alt,
    }


_COMMUNICATION_CHART = _chart(["channel", "feature", "provider_source", "platform", "audience", "skip_reason", "segment_source", "measurement"],
                            [], "{channel} activity in {period}")
# Cumulative progress overlaps: only exclusive current outcomes are stacked.
# Per-value kinds keep percentage/fraction lines separate from count stacks.
_COMMUNICATION_CHART["values"] = [
    {"field": field, "unit": "deliveries", "kind": "stacked_bar"} for field in MESSAGING_STATUS_COUNTS
] + [
    {"field": field, "unit": unit, "kind": "line"} for field, unit in (
        ("sent_count", "deliveries"), ("invalid_count", "deliveries"),
        ("bounced_count", "events"), ("complained_count", "events"),
        ("held_webhook_count", "receipts"), ("abandoned_webhook_count", "receipts"),
        ("inbox_created_count", "inbox rows"), ("inbox_read_count", "inbox rows"),
        ("delivery_rate", "ratio"), ("read_rate", "ratio"),
    )
]

COMMUNICATIONS_REPORT_DEFINITION = ReportDefinition(
    "communications-health", "apps.operations.reports_communications.build_communications_health",
    COMMUNICATION_FIELDS, required_action=rbac.Action.MANAGE_MAKERSPACE,
    title=gettext_noop("Communications health"), chart_hint="multi_line", version=4,
    grains=("day", "week", "month"),
    section_modules=("notifications", "email", "telegram", "slack", "mattermost", "discord", "webhook", "mobile", "sms", "whatsapp"),
    chart_spec=_COMMUNICATION_CHART,
)

HI_REPORT_DEFINITIONS = (
    ReportDefinition(
        "mobile-devices", "apps.operations.reports_mobile_devices.build_mobile_devices",
        MOBILE_DEVICE_FIELDS, ("mobile",), required_action=rbac.Action.MANAGE_MAKERSPACE,
        title=gettext_noop("Mobile devices and app sessions"), chart_hint="line", version=2, grains=("day", "week", "month"),
        chart_spec=_chart(["metric", "platform", "environment", "authority", "status"],
                          [("count", "observations")], "{metric}: {count} in {period}"),
    ),
    ReportDefinition(
        "mobile-auth", "apps.operations.reports_mobile_auth.build_mobile_auth",
        MOBILE_AUTH_FIELDS, ("mobile",), required_action=rbac.Action.MANAGE_MAKERSPACE,
        title=gettext_noop("Mobile authentication"), chart_hint="stacked_bar", version=2, grains=("day", "week", "month"),
        chart_spec=_chart(["metric", "platform", "environment", "outcome", "reason"],
                          [("count", "events")], "{metric}: {count} {outcome} in {period}"),
    ),
)

register_combine("communications-health", combine_communications)
register_combine("mobile-devices", partial(combine_counts, groups=MOBILE_DEVICE_GROUPS, counts=("count",)))
register_combine("mobile-auth", partial(combine_counts, groups=MOBILE_AUTH_GROUPS, counts=("count",)))

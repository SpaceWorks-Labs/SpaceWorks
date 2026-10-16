"""H/I report registration, chart contract and explicit organization combination."""

from functools import partial

from apps.accounts import rbac
from .org_report_aggregate import register_combine
from .report_types import ReportDefinition
from .reports_hi_common import combine_counts
from .report_fields_hi import (
    COMMUNICATION_COUNTS, COMMUNICATION_FIELDS, COMMUNICATION_GROUPS,
    MOBILE_AUTH_FIELDS, MOBILE_AUTH_GROUPS, MOBILE_DEVICE_FIELDS, MOBILE_DEVICE_GROUPS,
)


def _chart(series, values, alt):
    return {
        "series": series, "x": {"field": "period", "kind": "time"},
        "values": [{"field": field, "unit": unit} for field, unit in values],
        "currency_field": None, "partition": "tenant", "negatives": "clip",
        "truncation": None, "alt_template": alt,
    }


COMMUNICATIONS_REPORT_DEFINITION = ReportDefinition(
    "communications-health", "apps.integrations.reports_communications.build_communications_health",
    COMMUNICATION_FIELDS, required_action=rbac.Action.MANAGE_MAKERSPACE,
    title="Communications health", chart_hint="multi_line", version=2,
    grains=("day", "week", "month"),
    section_modules=("notifications", "email", "telegram", "slack", "mattermost", "discord", "webhook", "mobile"),
    chart_spec=_chart(["channel", "feature", "provider_source", "platform"],
                      [("sent_count", "deliveries"), ("failed_count", "deliveries"),
                       ("invalid_count", "deliveries"), ("suppressed_count", "deliveries"),
                       ("bounced_count", "events"), ("complained_count", "events"),
                       ("inbox_created_count", "inbox rows"), ("inbox_read_count", "inbox rows")],
                      "{channel} activity in {period}"),
)

HI_REPORT_DEFINITIONS = (
    ReportDefinition(
        "mobile-devices", "apps.operations.reports_mobile_devices.build_mobile_devices",
        MOBILE_DEVICE_FIELDS, ("mobile",), required_action=rbac.Action.MANAGE_MAKERSPACE,
        title="Mobile devices and app sessions", chart_hint="line", grains=("day", "week", "month"),
        chart_spec=_chart(["metric", "platform", "environment", "authority", "status"],
                          [("count", "observations")], "{metric}: {count} in {period}"),
    ),
    ReportDefinition(
        "mobile-auth", "apps.operations.reports_mobile_auth.build_mobile_auth",
        MOBILE_AUTH_FIELDS, ("mobile",), required_action=rbac.Action.MANAGE_MAKERSPACE,
        title="Mobile authentication", chart_hint="stacked_bar", grains=("day", "week", "month"),
        chart_spec=_chart(["metric", "platform", "environment", "outcome", "reason"],
                          [("count", "events")], "{metric}: {count} {outcome} in {period}"),
    ),
)

register_combine("communications-health", partial(
    combine_counts, groups=COMMUNICATION_GROUPS, counts=COMMUNICATION_COUNTS,
    rates=(("success_rate_percent", "sent_count", "delivery_count"),
           ("read_rate_percent", "inbox_read_count", "inbox_created_count")),
    latest=("last_activity_at",),
))
register_combine("mobile-devices", partial(combine_counts, groups=MOBILE_DEVICE_GROUPS, counts=("count",)))
register_combine("mobile-auth", partial(combine_counts, groups=MOBILE_AUTH_GROUPS, counts=("count",)))

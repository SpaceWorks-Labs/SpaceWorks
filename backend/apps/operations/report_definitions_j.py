"""Area J and superadmin analytics registration and organization combination."""

from django.utils.translation import gettext_lazy
from dataclasses import replace

from apps.accounts import rbac
from apps.operations.org_report_aggregate import register_combine
from apps.operations.org_reports_j import combine_audit, combine_device_health, combine_organization_membership, combine_presence
from apps.operations.report_definitions_coverage import COVERAGE_REPORT_DEFINITIONS
from apps.operations.report_types import ReportDefinition
from apps.operations.report_fields_j import (
    AUDIT_FIELDS, HOUR_FIELDS, PERSON_FIELDS, PRESENCE_FIELDS, DEVICE_FIELDS,
    HEALTH_FIELDS, ORGANIZATION_FIELDS, SERVICES_FIELDS, USAGE_FIELDS,
)
from apps.operations.reports_j_common import chart

GRAINS = ("day", "week", "month")
PATH = "apps.operations."


def _activity(key, fields, chart_spec, *, action=rbac.Action.VIEW_AUDIT, identity=False, hours=False):
    return ReportDefinition(
        key, f"{PATH}reports_j_activity.build_{key.replace('-', '_')}", fields,
        required_action=action, title=key.replace("-", " ").title(),
        grains=() if identity or hours else GRAINS,
        chart_hint="heatmap" if hours else "bar" if identity else "line", chart_spec=chart_spec,
        identity_bearing=identity, deployment_aggregate=not (identity or hours),
        schedulable=not (identity or hours),
    )


J_REPORT_DEFINITIONS = (
    ReportDefinition("device-health", f"{PATH}reports_j_devices.build_device_health", DEVICE_FIELDS,
                     ("devices",), required_action=rbac.Action.MANAGE_MAKERSPACE, title=gettext_lazy("Device health"),
                     grains=GRAINS, section_modules=("qr_print_batches",), chart_hint="stacked_bar",
                     chart_spec=chart("period", (("online_seconds", "seconds"), ("offline_seconds", "seconds"), ("unknown_seconds", "seconds"), ("command_success_percent", "percent"), ("labels_printed", "labels")), series=("device_id",))),
    _activity("presence-activity", PRESENCE_FIELDS,
              chart("period", (("visits", "visits"), ("unique_visitors", "visitors"), ("average_declared_presence_seconds", "seconds"))), action=rbac.Action.MANAGE_MEMBERS),
    _activity("presence-top-visitors", PERSON_FIELDS,
              chart("person_id", (("count", "visits"),), time=False, partition=None, top=10),
              action=rbac.Action.MANAGE_MEMBERS, identity=True),
    _activity("presence-activity-hours", HOUR_FIELDS,
              chart("hour", (("declared_presence_seconds", "seconds"),), series=("weekday",), time=False, partition=None),
              action=rbac.Action.MANAGE_MEMBERS, hours=True),
    _activity("audit-activity", AUDIT_FIELDS,
              chart("period", (("count", "actions"),), series=("action",), top=10)),
    _activity("audit-top-actors", PERSON_FIELDS,
              chart("person_id", (("count", "actions"),), time=False, partition=None, top=10), identity=True),
    _activity("audit-activity-hours", HOUR_FIELDS,
              chart("hour", (("count", "actions"),), series=("weekday",), time=False, partition=None), hours=True),
    ReportDefinition("organization-membership", f"{PATH}reports_j_organizations.build_organization_membership", ORGANIZATION_FIELDS,
                     required_action=rbac.Action.MANAGE_MAKERSPACE, title=gettext_lazy("Organization membership"), grains=GRAINS, schedulable=False,
                     chart_hint="funnel", chart_spec=chart("period", (("invitations", "invitations"), ("redeemed", "invitations"), ("active_memberships", "memberships")), series=("organization_id",))),
    replace(next(d for d in COVERAGE_REPORT_DEFINITIONS if d.key == "module-operational-health"),
            builder_path=f"{PATH}reports_j_health.build_module_operational_health", fields=HEALTH_FIELDS,
            version=3, grains=GRAINS, chart_hint="table", chart_spec=chart("period", (("delivery_count", "deliveries"), ("failure_count", "deliveries")), series=("module_key", "delivery_kind"))),
    ReportDefinition("platform-services", f"{PATH}reports_platform_services.build_platform_services", SERVICES_FIELDS,
                     required_action=rbac.Action.MANAGE_MAKERSPACE, platform_only=True, schedulable=False,
                     title=gettext_lazy("Platform services"), grains=GRAINS, chart_hint="stacked_bar", version=3,
                     section_modules=("sms", "whatsapp"),
                     chart_spec=chart("day", (("count", "operations"), ("amount", "currency")), series=("makerspace_id", "service", "purpose", "provider_source", "status", "bucket"), partition="currency", currency="currency")),
    ReportDefinition("platform-usage", f"{PATH}reports_platform_usage.build_platform_usage", USAGE_FIELDS,
                     required_action=rbac.Action.MANAGE_MAKERSPACE, platform_only=True, schedulable=False,
                     section_modules=("public_inventory", "request_workflow", "guest_handover", "bookings", "events", "membership", "member_accounts", "machines", "machine_service", "devices", "mobile"),
                     title=gettext_lazy("Platform usage"), grains=GRAINS, chart_hint="line",
                     chart_spec=chart("period", (("value", "unit"),), series=("makerspace_id", "metric", "entity_kind", "entity_id", "currency"),
                                      partition="unit", currency="currency", top=10)),
)
from apps.separability.tombstones import tombstoned_app_labels
if "presence" in tombstoned_app_labels():
    J_REPORT_DEFINITIONS = tuple(d for d in J_REPORT_DEFINITIONS if not d.key.startswith("presence-"))

register_combine("device-health", combine_device_health)
register_combine("presence-activity", combine_presence)
register_combine("audit-activity", combine_audit)
register_combine("organization-membership", combine_organization_membership)

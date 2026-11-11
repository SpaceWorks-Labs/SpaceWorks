"""Registration, disclosure boundaries and organization arithmetic (no database)."""

from dataclasses import replace
from types import SimpleNamespace

import pytest
from rest_framework.exceptions import PermissionDenied

from apps.accounts.models import User
from apps.operations.org_report_aggregate import aggregate_rows
from apps.operations.org_report_scope import EXCLUDED_ORGANIZATION_REPORT_KEYS
from apps.operations.org_report_strategies import STRATEGIES
from apps.operations.platform_scope import PlatformContext
from apps.operations.report_condition_metrics import condition_metrics
from apps.operations.report_definitions_j import J_REPORT_DEFINITIONS
from apps.operations.report_fields_j import DEVICE_SUM_FIELDS, ORGANIZATION_COUNTS
from apps.operations.report_registry import REPORT_REGISTRY, report_definition
from apps.operations.report_types import ReportNotFound
from apps.operations.report_validation import validate_report_definition
from apps.operations.reports_platform_services import build_platform_services
from apps.operations.reports_platform_usage import build_platform_usage


@pytest.mark.parametrize("key", [d.key for d in J_REPORT_DEFINITIONS])
def test_registration_chart_allowlist_and_organization_contract(key):
    definition = REPORT_REGISTRY[key]
    validate_report_definition(definition)
    assert definition.chart_spec
    if definition.deployment_aggregate:
        assert "makerspace_id" in definition.fields
    assert (key in STRATEGIES) != (key in EXCLUDED_ORGANIZATION_REPORT_KEYS)
    if key in STRATEGIES:
        strategy = STRATEGIES[key]
        assert set(strategy.total_fields) | set(strategy.breakdown_only_fields) == set(definition.fields) - {"makerspace_id"}
    if definition.grains:
        assert definition.grains == ("day", "week", "month")


@pytest.mark.parametrize("key", ["presence-top-visitors", "audit-top-actors"])
def test_rankings_are_tenant_only_unschedulable_and_org_excluded(key):
    d = REPORT_REGISTRY[key]
    assert d.identity_bearing and not d.schedulable and not d.deployment_aggregate
    assert key in EXCLUDED_ORGANIZATION_REPORT_KEYS
    with pytest.raises(ReportNotFound):
        report_definition(key, deployment_aggregate=True)


@pytest.mark.parametrize("key,builder", [("platform-services", build_platform_services), ("platform-usage", build_platform_usage)])
def test_platform_builders_refuse_unminted_context_and_tenant_lookup(key, builder):
    assert REPORT_REGISTRY[key].platform_only
    assert not REPORT_REGISTRY[key].schedulable
    for ctx in (None, SimpleNamespace(actor=User(role=User.Role.SUPERADMIN))):
        with pytest.raises(PermissionDenied):
            builder(platform_context=ctx)
    with pytest.raises(ReportNotFound):
        report_definition(key)
    with pytest.raises(TypeError):
        PlatformContext(User(role=User.Role.SUPERADMIN))


def test_device_rates_use_summed_terminal_denominators():
    base = {"period": "2026-10-12", "device_id": "a", **dict.fromkeys(DEVICE_SUM_FIELDS, 0)}
    a = {**base, "online_seconds": 1, "commands_acknowledged": 1}
    b = {**base, "offline_seconds": 9, "commands_failed": 9}
    row = aggregate_rows("device-health", [(1, [a]), (2, [b])], limit=10)[0]
    assert row["uptime_percent"] == row["command_success_percent"] == 10


def test_presence_combines_duration_samples_and_deduplicates_people():
    a = {"period": "2026-10-12", "visits": 1, "declared_presence_seconds": 10, "_visitors": {1}}
    b = {"period": "2026-10-12", "visits": 9, "declared_presence_seconds": 900, "_visitors": {1, 2}}
    row = aggregate_rows("presence-activity", [(1, [a]), (2, [b])], limit=10)[0]
    assert row["average_declared_presence_seconds"] == 91
    assert row["unique_visitors"] == 2
    assert "_visitors" not in row


def test_organization_funnel_never_multiplies_repeated_owner_links():
    cohort = {"period": "2026-10-12", "organization_id": 1, **dict.fromkeys(ORGANIZATION_COUNTS, 0), "invitations": 10, "redeemed": 1}
    row = aggregate_rows("organization-membership", [(1, [cohort]), (2, [cohort])], limit=10)[0]
    assert row["invitations"] == 10 and row["redemption_percent"] == 10


def test_numeric_conditions_and_extended_version_are_explicit():
    assert {"uptime_percent", "offline_incidents", "command_success_percent", "labels_printed"} <= set(condition_metrics(REPORT_REGISTRY["device-health"]))
    assert "average_declared_presence_seconds" in condition_metrics(REPORT_REGISTRY["presence-activity"])
    assert "redemption_percent" in condition_metrics(REPORT_REGISTRY["organization-membership"])
    assert REPORT_REGISTRY["module-operational-health"].version == 3  # lane R: SMS/WA cohorts
    assert not replace(REPORT_REGISTRY["audit-top-actors"], chart_spec=None).schedulable

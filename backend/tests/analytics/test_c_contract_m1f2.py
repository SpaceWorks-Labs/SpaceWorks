from dataclasses import replace

import pytest

from apps.accounts import rbac
from apps.operations.org_report_aggregate import aggregate_rows
from apps.operations.org_report_scope import EXCLUDED_ORGANIZATION_REPORT_KEYS
from apps.operations.org_report_strategies import STRATEGIES
from apps.operations.report_condition_metrics import condition_metrics
from apps.operations.report_definitions_machines import MACHINE_REPORT_KEYS as _ALL_MACHINE_REPORT_KEYS

# These M1F2 contract tests cover the original ten machine reports; the later families (machine-session-*, event
# machine use, consumables) are subject- or profile-scoped and have their own tests (l23_local, events, parity_0120).
MACHINE_REPORT_KEYS = frozenset({"machine-usage", "machine-usage-members", "machine-usage-heatmap", "machine-downtime",
                                 "maintenance-activity", "machine-service", "service-queue-times", "printer-jobs",
                                 "machine-errors", "warranty-expiry"}) & _ALL_MACHINE_REPORT_KEYS
from apps.operations.report_registry import REPORT_REGISTRY
from apps.operations.report_validation import validate_report_definition
from apps.operations.serializers_reports_machine_analytics import (
    MachineUsageV2Row, MachineMemberRow, MachineHeatmapRow, MachineDowntimeRow, MaintenanceActivityV2Row,
    MachineServiceV2Row, ServiceQueueTimesRow, PrinterJobsRow, MachineErrorsRow, WarrantyExpiryRow,
)
from tests.operations.report_assertions import assert_report_disclosure_safe


@pytest.mark.parametrize("key", sorted(MACHINE_REPORT_KEYS))
def test_machine_definitions_declare_privacy_grains_action_and_chart(key):
    definition = REPORT_REGISTRY[key]
    assert definition.required_action == rbac.Action.MANAGE_MACHINES
    validate_report_definition(definition)
    assert definition.chart_spec
    assert definition.grains == (() if key == "warranty-expiry" else ("day", "week", "month"))
    assert definition.identity_bearing == (key == "machine-usage-members")
    assert definition.deployment_aggregate == (key != "machine-usage-members")
    assert definition.schedulable == (key != "machine-usage-members")
    if key in {"machine-usage", "maintenance-activity", "machine-service"}:
        assert definition.version == 2
    if key in {"machine-usage-members", "machine-usage-heatmap", "service-queue-times"}:
        assert key in EXCLUDED_ORGANIZATION_REPORT_KEYS
        assert key not in STRATEGIES
    else:
        assert set(STRATEGIES[key].total_fields) == set(definition.fields) - {"makerspace_id"}
    if definition.schedulable:
        assert condition_metrics(definition)
    assert_report_disclosure_safe(definition.chart_spec)


# R3: L23 (95a1f393) added the machine-session-* reports with their own row serializers and
# tests (tests/l23_local); this pairing covers the M1F2 reports only.
# The later machine reports (machine-session-*, machine-event-*, consumables) own their row tests elsewhere.
_M1F2_KEYS = frozenset({"machine-usage", "machine-usage-members", "machine-usage-heatmap", "machine-downtime",
                        "maintenance-activity", "machine-service", "service-queue-times", "printer-jobs",
                        "machine-errors", "warranty-expiry"})


@pytest.mark.parametrize("key,row", list(zip(sorted(k for k in MACHINE_REPORT_KEYS if k in _M1F2_KEYS), [
    MachineDowntimeRow, MachineErrorsRow, MachineServiceV2Row, MachineUsageV2Row, MachineHeatmapRow,
    MachineMemberRow, MaintenanceActivityV2Row, PrinterJobsRow, ServiceQueueTimesRow, WarrantyExpiryRow,
], strict=True)))
def test_openapi_rows_match_public_allowlists(key, row):
    assert set(row().fields) - {"makerspace_id"} == set(REPORT_REGISTRY[key].fields) - {"makerspace_id"}


def test_service_rate_combines_summed_samples_in_each_period():
    def row(count, failed, period="2026-10-12"):
        return dict(period=period, row_kind="machine", machine_id=1, completed_count=count, failed_count=failed)
    combined = aggregate_rows("machine-service", [(1, [row(0, 1)]), (2, [row(9, 0), row(0, 1, "2026-10-19")])], limit=100)
    assert [r["failure_rate"] for r in combined] == [10, 100]
    assert combined[0]["completed_count"] == 9
    assert combined[0]["failed_count"] == 1
    assert_report_disclosure_safe(combined)


def test_maintenance_averages_use_cost_and_interval_denominators():
    rows = [(1, [dict(period="2026-10-12", machine_id=1, total_cost=10, costed_log_count=1,
                     _interval_total_days=2, _interval_gap_count=1)]),
            (2, [dict(period="2026-10-12", machine_id=1, total_cost=90, costed_log_count=9,
                      _interval_total_days=18, _interval_gap_count=9)])]
    total = aggregate_rows("maintenance-activity", rows, limit=10)[0]
    assert total["average_cost"] == 10
    assert total["average_interval_days"] == 2


def test_usage_rollup_never_adds_different_measures_or_types():
    rows = [(1, [dict(period="2026-10-12", measure="booked", machine_id=None, machine_type_id=1, booked_hours=3)]),
            (2, [dict(period="2026-10-12", measure="booked", machine_id=None, machine_type_id=1, booked_hours=4),
                 dict(period="2026-10-12", measure="manual", machine_id=8, machine_type_id=1, manual_hours=5),
                 dict(period="2026-10-12", measure="booked", machine_id=None, machine_type_id=2, booked_hours=9)])]
    total = aggregate_rows("machine-usage", rows, limit=10)
    assert len(total) == 3
    assert next(r for r in total if r["measure"] == "booked" and r["machine_type_id"] == 1)["booked_hours"] == 7


def test_member_report_cannot_accidentally_be_enabled_for_delivery():
    with pytest.raises(ValueError):
        validate_report_definition(replace(REPORT_REGISTRY["machine-usage-members"], schedulable=True))


@pytest.mark.parametrize("key,dimension,numeric", [
    ("machine-downtime", "status", "status_hours"),
    ("printer-jobs", "state", "job_count"),
    ("machine-errors", "severity", "error_count"),
])
def test_organization_counts_keep_status_and_period_partitions(key, dimension, numeric):
    base = {"period": "2026-10-12", "machine_id": 1, dimension: "first", numeric: 2}
    total = aggregate_rows(key, [(1, [base]), (2, [{**base, numeric: 3}, {**base, dimension: "second", numeric: 7}])], limit=10)
    assert len(total) == 2
    assert {row[dimension]: row[numeric] for row in total} == {"first": 5, "second": 7}
    assert_report_disclosure_safe(total)


def test_organization_warranties_remain_distinct_by_warranty_id():
    source = [(1, [dict(warranty_id=1, machine_name="Same name", days_until_expiry=2)]),
              (2, [dict(warranty_id=2, machine_name="Same name", days_until_expiry=9)])]
    total = aggregate_rows("warranty-expiry", source, limit=10)
    assert {row["warranty_id"]: row["days_until_expiry"] for row in total} == {1: 2, 2: 9}

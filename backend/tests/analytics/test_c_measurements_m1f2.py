from decimal import Decimal
from types import SimpleNamespace
from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from apps.machines.models import ServiceQueue, MachineServiceRequest
from apps.operations import reports
from apps.operations.report_definitions_machines import MACHINE_REPORT_KEYS as _ALL_MACHINE_REPORT_KEYS

# These M1F2 contract tests cover the original ten machine reports; the later families (machine-session-*, event
# machine use, consumables) are subject- or profile-scoped and have their own tests (l23_local, events, parity_0120).
MACHINE_REPORT_KEYS = frozenset({"machine-usage", "machine-usage-members", "machine-usage-heatmap", "machine-downtime",
                                 "maintenance-activity", "machine-service", "service-queue-times", "printer-jobs",
                                 "machine-errors", "warranty-expiry"}) & _ALL_MACHINE_REPORT_KEYS
from apps.operations.reports_machine_downtime import _period_segments
from apps.operations.reports_machine_heatmap import hour_cells
from apps.operations.reports_machine_queue import percentile
from apps.operations.reports_machine_usage_v2 import _top_five_series
from tests.operations.report_assertions import assert_report_disclosure_safe
from .c_helpers_m1f2 import at, c_lab


@pytest.mark.django_db
@pytest.mark.parametrize("key", sorted(MACHINE_REPORT_KEYS - {"warranty-expiry"}))
@pytest.mark.parametrize("grain,expected", [("day", "2026-10-12"), ("week", "2026-10-12"), ("month", "2026-10-01")])
def test_grains_use_real_calendar_periods(c_lab, key, grain, expected):
    result = reports.report_data(key, c_lab["space"].pk, actor=c_lab["owner"], date_range=c_lab["date_range"], grain=grain)
    assert result["typed_rows"]
    assert {row["period"] for row in result["typed_rows"] if row["period"]} >= {expected}
    if key != "machine-downtime":
        assert all(row["period"] in {None, expected} for row in result["typed_rows"])
    assert_report_disclosure_safe(result)


@pytest.mark.django_db
def test_usage_measures_and_members_use_recorded_values_separately(c_lab):
    result = reports.report_data("machine-usage", c_lab["space"].pk, actor=c_lab["manager"], date_range=c_lab["date_range"])
    sums = {field: sum(Decimal(row.get(field) or 0) for row in result["typed_rows"]) for field in ("service_hours", "manual_hours", "booked_hours")}
    assert sums == {"service_hours": Decimal("1.25"), "manual_hours": Decimal(5), "booked_hours": Decimal(3)}
    assert all(row["machine_id"] is None for row in result["typed_rows"] if row["measure"] == "booked")
    members = reports.report_data("machine-usage-members", c_lab["space"].pk, actor=c_lab["owner"], date_range=c_lab["date_range"])["typed_rows"]
    assert sum(Decimal(row["hours"]) for row in members if row["member_id"] is None) == 6  # both machine types


@pytest.mark.django_db
def test_heatmap_splits_intervals_and_omits_undated_manual_history(c_lab):
    rows = reports.report_data("machine-usage-heatmap", c_lab["space"].pk, actor=c_lab["manager"], date_range=c_lab["date_range"])["typed_rows"]
    manual_rows = [row for row in rows if row["measure"] == "manual"]
    assert {row["hour"]: Decimal(row["manual_hours"]) for row in manual_rows} == {9: Decimal("0.50"), 10: Decimal(1), 11: Decimal("0.50")}
    assert {row["weekday"] for row in rows} == {0}
    assert sum(Decimal(row.get("service_hours") or 0) for row in rows) == 2  # wall-clock intervals, not recorded metering
    assert sum(Decimal(row.get("booked_hours") or 0) for row in rows) == 3


@pytest.mark.django_db
def test_downtime_unknown_then_last_known_state_without_current_status_backfill(c_lab):
    # This is a completed historical window; wall time must be after its end.
    with patch("django.utils.timezone.now", return_value=at(20, 0)):
        rows = reports.report_data("machine-downtime", c_lab["space"].pk, actor=c_lab["manager"], date_range=c_lab["date_range"])["typed_rows"]
    assert sum(Decimal(row["status_hours"]) for row in rows) == 168
    assert sum(Decimal(row["status_hours"]) for row in rows if row["status"] == "unknown") == 9
    rows = reports.report_data("machine-downtime", c_lab["space"].pk, actor=c_lab["manager"], date_range=(at(13, 0), at(14, 0)))["typed_rows"]
    assert {row["status"] for row in rows} == {"maintenance"}
    assert sum(Decimal(row["status_hours"]) for row in rows) == 24


@pytest.mark.django_db
def test_downtime_caps_future_window_at_last_observable_instant(c_lab):
    with patch("django.utils.timezone.now", return_value=at(13, 6)):
        rows = reports.report_data("machine-downtime", c_lab["space"].pk, actor=c_lab["manager"],
            date_range=(at(13, 0), at(14, 0)))["typed_rows"]
        assert {row["status"] for row in rows} == {"maintenance"}
        assert sum(Decimal(row["status_hours"]) for row in rows) == 6
        assert reports.report_data("machine-downtime", c_lab["space"].pk, actor=c_lab["manager"],
            date_range=(at(14, 0), at(15, 0)))["typed_rows"] == []


@pytest.mark.django_db
def test_failure_rate_terminal_clock_and_queue_stage_samples(c_lab):
    service = reports.report_data("machine-service", c_lab["space"].pk, actor=c_lab["manager"], date_range=c_lab["date_range"])["typed_rows"]
    machine = next(row for row in service if row["row_kind"] == "machine")
    assert machine["failure_rate"] == 50
    assert machine["failed_partial_hours"] == "0.25"
    queue = reports.report_data("service-queue-times", c_lab["space"].pk, actor=c_lab["manager"], date_range=c_lab["date_range"])["typed_rows"]
    assert {row["stage"]: row["samples"] for row in queue} == {"created→accepted": 2, "accepted→started": 2, "started→completed": 1, "completed→collected": 1}
    assert {row["median_minutes"] for row in queue} == {"60.00", "120.00"}


@pytest.mark.django_db
def test_unallocated_queue_jobs_follow_queue_type_scope(c_lab):
    queue = ServiceQueue.objects.create(makerspace=c_lab["space"], machine_type=c_lab["printer"].machine_type, name="Printer intake")
    with patch("django.utils.timezone.now", return_value=at(12, 6)):
        MachineServiceRequest.objects.create(makerspace=c_lab["space"], queue=queue, requester=c_lab["member"], accepted_at=at(12, 7))
    data = reports.report_data("machine-service", c_lab["space"].pk, actor=c_lab["manager"], date_range=c_lab["date_range"])
    assert sum(row["submitted"] or 0 for row in data["typed_rows"]) == 2


@pytest.mark.django_db
def test_health_and_warranty_counts_use_their_tracked_sources(c_lab):
    space_id = c_lab["space"].pk
    for key, field in (("printer-jobs", "job_count"), ("machine-errors", "error_count")):
        rows = reports.report_data(key, space_id, actor=c_lab["manager"], date_range=c_lab["date_range"])["typed_rows"]
        assert len(rows) == 1 and rows[0][field] == 1
    maintenance = reports.report_data("maintenance-activity", space_id, actor=c_lab["manager"], date_range=c_lab["date_range"])["typed_rows"]
    assert sum(row["log_count"] or 0 for row in maintenance) == 1
    assert sum(row["active_schedules"] or 0 for row in maintenance) == 1
    logs = next(row for row in maintenance if row["period"])
    assert logs["currency"] == "unknown"
    assert logs["average_cost"] == "12.50"
    warranties = reports.report_data("warranty-expiry", space_id, actor=c_lab["manager"], date_range=c_lab["date_range"])["typed_rows"]
    assert len(warranties) == 1
    assert warranties[0]["warranty_expires_on"] == at(18).date()
    assert reports.report_data("warranty-expiry", space_id, actor=c_lab["manager"], date_range=(at(19, 0), at(20, 0)))["typed_rows"] == []


@pytest.mark.django_db
def test_local_week_buckets_cross_utc_sunday_into_tenant_monday(c_lab):
    space = c_lab["space"]
    space.timezone = "Asia/Kolkata"
    space.save(update_fields=["timezone"])
    # Sunday 23:30 UTC is Monday 05:00 in the tenant.
    from apps.machines.models import MachineUsageEntry
    with patch("django.utils.timezone.now", return_value=at(11, 23, 30)):
        MachineUsageEntry.objects.create(machine=c_lab["laser"], hours=Decimal(8))
    rows = reports.report_data("machine-usage", space.pk, actor=c_lab["manager"],
                               date_range=(at(11, 20), at(12, 0)), grain="week")["typed_rows"]
    assert {r["period"] for r in rows} == {"2026-10-12"}
    assert sum(Decimal(r["manual_hours"] or 0) for r in rows) == 8


def test_dst_preserves_real_elapsed_hours_and_repeated_local_hour():
    space = SimpleNamespace(timezone="America/New_York")
    start = datetime(2026, 11, 1, 4, tzinfo=timezone.utc)
    end = datetime(2026, 11, 2, 5, tzinfo=timezone.utc)
    cells = list(hour_cells(start, end, space))
    assert sum(value for _, value in cells) == 25
    assert sum(value for (_, _, hour), value in cells if hour == 1) == 2
    assert sum(value for _, value in _period_segments(start, end, "day", space)) == 25


def test_continuous_percentiles_and_top_five_keep_other_total():
    assert percentile([Decimal(0), Decimal(100)], .9) == 90
    rows = [dict(makerspace_id=1, measure="manual", period="2026-10-12", machine_id=i, machine_name=str(i), machine_type_id=1, machine_type="Laser", entries=1, hours=Decimal(i)) for i in range(1, 8)]
    projected = _top_five_series(rows)
    assert len(projected) == 6
    assert sum(row["hours"] for row in projected) == 28
    assert next(row for row in projected if row["machine_name"] == "Other")["hours"] == 3

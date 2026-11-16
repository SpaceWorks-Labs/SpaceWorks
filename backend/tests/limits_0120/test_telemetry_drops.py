"""Decision 328a: samples dropped at the `adapter_telemetry_points` limit are counted per space per day and shown."""
from datetime import timedelta

import pytest
from django.utils import timezone

from apps.devices.models import AdapterTelemetryDrop
from apps.devices.telemetry_drops import dropped_since, record_drop
from tests.makerspaces.l4_helpers import space_with_manager
from tests.open_items_0120.test_platform_credential_limits import _limit

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _off(settings):
    settings.PLATFORM_DOMAIN_SUFFIX = ""
    settings.MANAGED_PLANS_ENABLED = False


def test_drops_accumulate_in_one_row_per_space_per_day():
    space, _m = space_with_manager("td-count")
    other, _o = space_with_manager("td-other")
    record_drop(space.pk, 3)
    record_drop(space.pk, 4)
    record_drop(other.pk, 1)
    assert AdapterTelemetryDrop.objects.filter(makerspace=space).count() == 1
    assert dropped_since(space.pk, 7) == 7 and dropped_since(other.pk, 7) == 1


def test_old_days_fall_outside_the_window():
    space, _m = space_with_manager("td-window")
    AdapterTelemetryDrop.objects.create(makerspace=space, day=timezone.now().date() - timedelta(days=10), count=99)
    record_drop(space.pk, 2)
    assert dropped_since(space.pk, 7) == 2 and dropped_since(space.pk, 30) == 101


def test_the_hundred_percent_notice_names_the_dropped_samples():
    from apps.managed_hosting.limit_notices import notify_threshold
    from apps.notifications.models_inbox import NotificationInboxRow
    space, manager = space_with_manager("td-notice")
    record_drop(space.pk, 42)
    notify_threshold(space, "adapter_telemetry_points", "device telemetry samples kept", 100, 100, "2026-11")
    row = NotificationInboxRow.objects.get(makerspace=space, user=manager, event="platform_limit.reached")
    assert "42 telemetry samples were dropped" in row.summary


def test_the_activity_report_has_a_dropped_samples_row():
    from apps.operations.reports_r2_devices import _adapter_rows
    space, _m = space_with_manager("td-report")
    record_drop(space.pk, 5)
    start, end = timezone.now() - timedelta(days=1), timezone.now() + timedelta(days=1)
    assert dict(_adapter_rows(space, start, end))["telemetry_samples_dropped"] == 5


def test_adapter_summary_reads_the_counter():
    from pathlib import Path
    source = (Path(__file__).resolve().parents[2] / "apps/devices/services_adapter_admin.py").read_text(encoding="utf8")
    assert '"telemetry_dropped_7d": dropped_since(device.makerspace_id, 7)' in source


def test_the_ingest_seam_drops_and_counts_at_the_limit():
    from apps.managed_hosting.extra_quotas import extra_quota_allows
    space, _m = space_with_manager("td-seam")
    _limit(space, adapter_telemetry_points=0)
    assert extra_quota_allows(space, "adapter_telemetry_points", adding=2) is False
    record_drop(space.pk, 2)  # what _store does when the answer is False
    assert dropped_since(space.pk, 1) == 2

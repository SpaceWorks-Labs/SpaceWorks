"""The heartbeat's status snapshot: bounded, finite, clamped, idempotent and rate-limited."""
import time
from datetime import timedelta
from decimal import Decimal

import pytest

from apps.devices.models import PrinterStatusSnapshot
from tests.devices.sim_agent import integrated_case, snapshot

pytestmark = pytest.mark.django_db(transaction=True)


def test_out_of_range_numbers_are_clamped_not_refused():
    case = integrated_case("snap-clamp")
    response = case["agent"].heartbeat(snapshot(progress_percent=250, layer_current=-3, layer_total=10**9,
                                                temperatures={"nozzle": 9999, "bed": -500.25},
                                                spools=[{"slot": 1, "remaining_percent": 180}]))
    assert response.status_code == 200 and response.data["status_snapshot"] == "stored"
    row = PrinterStatusSnapshot.objects.get(device=case["device"])
    assert (row.progress_percent, row.layer_current, row.layer_total) == (100, 0, 100000)
    assert (row.nozzle_temp_c, row.bed_temp_c, row.chamber_temp_c) == (Decimal("400.0"), Decimal("-40.0"), None)
    assert row.spools == [{"slot": 1, "material": "", "colour": "", "remaining_percent": 100}]


@pytest.mark.parametrize("bad", [
    {"state": "melting"}, {"schema_version": 2}, {"gcode": "G28"}, {"clear_token": "has space"},
    {"spools": [{"slot": 0}] * 17}, {"spools": [{"slot": 1}, {"slot": 1}]}, {"progress_percent": "lots"},
    {"temperatures": {"nozzle": True}}, {"temperatures": {"hotend2": 200}}, {"observed_at": "now"},
    {"layer_total": None, "spools": [{"slot": 99}]}, {"clear_token": "x" * 65},
])
def test_kinds_sizes_and_unknown_fields_are_refused(bad):
    case = integrated_case(f"snap-bad-{abs(hash(str(bad))) % 10**8}")
    assert case["agent"].heartbeat(snapshot(**bad)).status_code == 400
    assert not PrinterStatusSnapshot.objects.exists()


def test_an_older_or_repeated_snapshot_changes_nothing_and_bursts_are_throttled():
    case = integrated_case("snap-idempotent")
    now = int(time.time())
    assert case["agent"].heartbeat(snapshot(observed_at=now - 30)).data["status_snapshot"] == "stored"
    assert case["agent"].heartbeat(snapshot(observed_at=now - 30, state="idle")).data["status_snapshot"] == "stale"
    assert case["agent"].heartbeat(snapshot(observed_at=now - 60)).data["status_snapshot"] == "stale"
    assert case["agent"].heartbeat(snapshot(observed_at=now - 20)).data["status_snapshot"] == "throttled"
    assert PrinterStatusSnapshot.objects.get().state == "printing"
    PrinterStatusSnapshot.objects.update(received_at=PrinterStatusSnapshot.objects.get().received_at - timedelta(seconds=10))
    assert case["agent"].heartbeat(snapshot(observed_at=now - 10, state="paused")).data["status_snapshot"] == "stored"
    assert PrinterStatusSnapshot.objects.get().state == "paused"


def test_a_future_observation_is_refused_and_the_device_is_still_seen():
    case = integrated_case("snap-future")
    assert case["agent"].heartbeat(snapshot(observed_at=int(time.time()) + 3600)).status_code == 400
    assert not PrinterStatusSnapshot.objects.exists()


def test_the_snapshot_never_changes_machine_status():
    case = integrated_case("snap-machine")
    before = case["machine"].status
    case["agent"].heartbeat(snapshot(state="error"))
    case["machine"].refresh_from_db()
    assert case["machine"].status == before

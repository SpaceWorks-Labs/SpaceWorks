"""Decision 220(d)4: maintenance lockout and the queue ETA read "today" as the SPACE's local
date, together, so a space far from the server never locks or unlocks a day early or late."""

from datetime import date

import pytest

from apps.machines.lockout import blocking_schedules
from apps.machines.service_queue_eta import machine_queue_summaries_for
from apps.maintenance.models import MaintenanceSchedule
from apps.makerspaces import local_time
from tests.machines.eta_helpers import NOW, world

pytestmark = pytest.mark.django_db

# NOW is 2026-10-18 10:00 UTC (the server's TIME_ZONE): already the 19th at UTC+14 and
# still the 17th at UTC-11.
AHEAD, BEHIND = "Pacific/Kiritimati", "Pacific/Pago_Pago"


def _space(slug, zone):
    w = world(slug, machines=1)
    w.space.timezone = zone
    w.space.enabled_features = sorted(set(w.space.enabled_features or []) | {"machines.maintenance"})
    w.space.save(update_fields=["timezone", "enabled_features"])
    w.machines[0].makerspace.refresh_from_db()
    return w


def _due(w, day):
    MaintenanceSchedule.objects.create(machine=w.machines[0], description="Interlock check", interval_days=30,
                                       next_due=day, blocks_use=True)


def _eta_locked(w):
    summary = machine_queue_summaries_for(w.machines, now=NOW)[w.machines[0].pk]
    return summary["confidence"] == "unavailable"


@pytest.fixture(autouse=True)
def frozen_local_now(monkeypatch):
    monkeypatch.setattr(local_time, "local_now", lambda makerspace: local_time.to_local(makerspace, NOW))


def test_a_space_ahead_of_the_server_locks_on_its_own_due_date():
    w = _space("lock-ahead", AHEAD)
    _due(w, date(2026, 10, 19))
    assert blocking_schedules(w.machines[0])  # the server's date is still the 18th
    assert _eta_locked(w)


def test_a_space_behind_the_server_is_not_locked_a_day_early():
    w = _space("lock-behind", BEHIND)
    _due(w, date(2026, 10, 18))
    assert not blocking_schedules(w.machines[0])  # the server's date already reached the 18th
    assert not _eta_locked(w)
    _due(w, date(2026, 10, 17))
    assert blocking_schedules(w.machines[0]) and _eta_locked(w)

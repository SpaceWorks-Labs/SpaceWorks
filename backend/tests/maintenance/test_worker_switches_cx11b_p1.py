"""Real reminder source admission: no work while off, same occurrence once after restore."""
from datetime import timedelta

import pytest
from django.db import connection
from django.utils import timezone

from apps.maintenance.models import MaintenanceSchedule
from apps.maintenance.repairs.maintenance_subjects import create_schedule
from apps.operations.models_reminders import ReminderSchedule
from apps.operations.reminder_sweeper import run_reminder_sweep
from tests.maintenance.l16_helpers import world
from tests.modules.switch_matrix_object_helpers import retained
from tests.modules.test_switch_matrix_objects_rest_support import _no_write, switch

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.area_inventory,
              pytest.mark.area_machines, pytest.mark.area_bookings]
ROWS = [("inventory.maintenance_reminders", "maintenance.items", "inventory.maintenance", None),
        ("bookings.room_maintenance_reminders", "maintenance.rooms", "bookings.room_maintenance", "bookings"),
        ("maintenance.reminders", "maintenance.due", "machines.maintenance", "machines")]
CASES = [(feature, source, key) for feature, source, parent, module in ROWS
         for key in (feature, parent, "notifications", *([module] if module else ["loans.enabled"]))]


@pytest.mark.parametrize("feature,source,key", CASES)
def test_reminder_worker_off_preserves_schedule_and_restore_dispatches_once(feature, source, key, monkeypatch):
    w = world("p1-reminder")
    w.space.enabled_modules = sorted(set(w.space.enabled_modules) | {"notifications"})
    w.space.enabled_features = sorted(set(w.space.enabled_features) | {feature})
    w.space.save(update_fields=["enabled_modules", "enabled_features"])
    now = timezone.now()
    due = now.date() - timedelta(days=10)
    sent = []
    if source == "maintenance.due":
        row = MaintenanceSchedule.objects.create(machine=w.machine, description="Retained machine inspection",
            interval_days=30, next_due=due, created_by=w.manager)
        monkeypatch.setattr("apps.maintenance.reminders.notify_maintenance_lifecycle",
                            lambda schedule, event: sent.append((schedule.pk, event)))
    else:
        room = source == "maintenance.rooms"
        row = create_schedule(w.manager, w.space, subject_type="bookable_space" if room else "inventory_product",
            subject=w.room if room else w.product, description="Retained inspection", interval_days=30, next_due=due)
        monkeypatch.setattr("apps.maintenance.reminders_subjects.notify",
                            lambda schedule, event: sent.append((schedule.pk, event)))
    before = retained({"schedule": row})
    original = switch(w.space, key)
    with connection.execute_wrapper(_no_write):
        counts = run_reminder_sweep(now=now, source_keys=[source])
    assert counts == {"dispatched": 0, "skipped": 1, "failed": 0}
    assert sent == []
    assert retained({"schedule": row}) == before
    assert ReminderSchedule.objects.filter(makerspace=w.space, source=source).count() == 0
    switch(w.space, key, original=original)
    counts = run_reminder_sweep(now=now, source_keys=[source])
    assert counts == {"dispatched": 1, "skipped": 0, "failed": 0}
    assert sent == [(row.pk, "overdue")]
    assert run_reminder_sweep(now=now, source_keys=[source]) == {"dispatched": 0, "skipped": 0, "failed": 0}
    assert sent == [(row.pk, "overdue")]
    assert retained({"schedule": row}) == before

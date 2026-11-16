"""GAP2 M2: due-soon and overdue reminders for item and room maintenance. Local only."""

from datetime import date, datetime, timezone as utc
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest

from apps.integrations.notification_catalog import FEATURE_EVENTS
from apps.maintenance import reminders_subjects as subject_reminders
from apps.maintenance.repairs import maintenance_subjects as subjects
from apps.makerspaces.capabilities import FEATURES
from apps.operations.models_reminders import ReminderSchedule
from apps.operations.reminder_registry import registered_sources
from apps.operations.reminder_sweeper import run_reminder_sweep
from tests.maintenance.l16_helpers import switch, world

pytestmark = pytest.mark.django_db(transaction=True)
KEYS = ("inventory.maintenance_reminders", "bookings.room_maintenance_reminders")


def reminder_world(slug, zone="UTC"):
    w = world(slug)
    w.space.timezone = zone
    w.space.enabled_modules = sorted(set(w.space.enabled_modules) | {"notifications"})
    w.space.save(update_fields=["timezone", "enabled_modules"])
    switch(w.space, on=KEYS)
    return w


def schedule(w, next_due, subject_type="inventory_product", subject=None):
    return subjects.create_schedule(w.manager, w.space, subject_type=subject_type, subject=subject or w.product,
                                    description="Clean tips", interval_days=30, next_due=next_due)


@pytest.fixture
def notices(monkeypatch):
    sent = []
    monkeypatch.setattr(subject_reminders, "notify", lambda row, kind: sent.append((row.pk, kind)))
    return sent


def test_the_two_switches_are_default_on_and_need_the_parent_maintenance_key_and_notifications():
    for key, parent in zip(KEYS, ("inventory.maintenance", "bookings.room_maintenance")):
        definition = FEATURES[key]
        assert definition.default_enabled and definition.requires_features == (parent,)
        assert "notifications" in definition.requires_modules
    assert {"maintenance.items", "maintenance.rooms"} <= {source.key for source in registered_sources()}
    for family in ("hardware_requests", "bookings"):
        assert {"maintenance_due_soon", "maintenance_overdue"} <= set(FEATURE_EVENTS[family])


def test_due_soon_then_overdue_once_per_occurrence_in_local_time_and_a_run_rearms(notices):
    w = reminder_world("gap-m2-once", "Asia/Kolkata")
    row = schedule(w, date(2026, 10, 19))
    early = datetime(2026, 10, 17, 18, 0, tzinfo=utc.utc)  # Oct 17 23:30 locally: not yet the day before
    run_reminder_sweep(now=early)
    assert notices == []
    now = datetime(2026, 10, 17, 18, 40, tzinfo=utc.utc)  # October 18 locally
    run_reminder_sweep(now=now)
    run_reminder_sweep(now=now)
    assert notices == [(row.pk, "due_soon")]
    marker = ReminderSchedule.objects.get(source="maintenance.items", kind="due_soon", makerspace=w.space)
    assert marker.due_at == datetime(2026, 10, 17, 18, 30, tzinfo=utc.utc)
    overdue = datetime(2026, 10, 19, 18, 40, tzinfo=utc.utc)  # October 20 locally
    run_reminder_sweep(now=overdue)
    run_reminder_sweep(now=overdue)
    assert notices[-1] == (row.pk, "overdue") and len(notices) == 2
    subjects.run(w.manager, row, summary="Done", performed_at=datetime(2026, 11, 20, 12, tzinfo=utc.utc))
    run_reminder_sweep(now=datetime(2026, 12, 20, 12, tzinfo=utc.utc))
    assert len(notices) == 3 and notices[-1][1] == "due_soon"


def test_rooms_use_their_own_source(notices):
    w = reminder_world("gap-m2-room")
    row = schedule(w, date(2026, 10, 10), "bookable_space", w.room)
    run_reminder_sweep(now=datetime(2026, 10, 12, tzinfo=utc.utc))
    assert notices == [(row.pk, "overdue")]
    assert ReminderSchedule.objects.filter(source="maintenance.rooms", makerspace=w.space).exists()
    assert not ReminderSchedule.objects.filter(source="maintenance.items", makerspace=w.space).exists()


@pytest.mark.parametrize("off", ["inventory.maintenance_reminders", "inventory.maintenance"])
def test_switching_the_reminder_or_the_parent_off_sends_nothing_and_keeps_the_schedule(notices, off):
    w = reminder_world("gap-m2-off")
    row = schedule(w, date(2026, 10, 10))
    switch(w.space, off=(off,))
    run_reminder_sweep(now=datetime(2026, 10, 12, tzinfo=utc.utc))
    assert notices == [] and not ReminderSchedule.objects.filter(source="maintenance.items").exists()
    row.refresh_from_db()
    assert row.is_active


def test_notifications_module_off_leaves_the_sources_inert(notices):
    from tests.module_helpers import disable_module
    w = reminder_world("gap-m2-notif")
    schedule(w, date(2026, 10, 10))
    disable_module(w.space, "notifications")
    run_reminder_sweep(now=datetime(2026, 10, 12, tzinfo=utc.utc))
    assert notices == []


def test_build_refuses_a_foreign_space_a_moved_due_date_and_a_paused_schedule():
    w = reminder_world("gap-m2-build")
    other = reminder_world("gap-m2-build-other")
    row = schedule(w, date(2026, 10, 10))
    due = subject_reminders.due_at(w.space, row, "overdue")
    marker = ReminderSchedule(subject=f"{row.pk}:2026-10-10", kind="overdue", due_at=due, offset_seconds=0)
    tz = ZoneInfo("UTC")
    assert subject_reminders._build(w.space, marker, due, tz, area="items").event == "overdue"
    assert subject_reminders._build(other.space, marker, due, tz, area="items") is None
    assert subject_reminders._build(w.space, marker, due, tz, area="rooms") is None
    stale = ReminderSchedule(subject=f"{row.pk}:2026-09-10", kind="overdue", due_at=due, offset_seconds=0)
    assert subject_reminders._build(w.space, stale, due, tz, area="items") is None
    subjects.update_schedule(w.manager, row, is_active=False)
    assert subject_reminders._build(w.space, marker, due, tz, area="items") is None


def test_delivery_recheck_drops_a_notice_once_the_switch_is_off_or_the_date_moved():
    w = reminder_world("gap-m2-eligible")
    row = schedule(w, date(2020, 1, 10))
    event = "maintenance_overdue"
    envelope = SimpleNamespace(event=event, makerspace_id=w.space.pk, makerspace=w.space, source_id=row.pk,
                               audience="staff", revision=subject_reminders.version(row, event))
    assert subject_reminders.eligible(envelope)
    assert not subject_reminders.eligible(SimpleNamespace(**{**vars(envelope), "audience": "requester"}))
    switch(w.space, off=("inventory.maintenance_reminders",))
    assert not subject_reminders.eligible(envelope)
    switch(w.space, on=("inventory.maintenance_reminders",))
    subjects.update_schedule(w.manager, row, next_due=date(2099, 1, 1))
    assert not subject_reminders.eligible(envelope)


def test_the_notice_reaches_the_inventory_managers_family_without_contact_details():
    from apps.integrations.models_contract import NotificationEnvelope
    w = reminder_world("gap-m2-fanout")
    row = schedule(w, date(2020, 1, 10))
    subject_reminders.notify(row, "overdue")
    envelopes = NotificationEnvelope.objects.filter(makerspace=w.space, source_kind=subject_reminders.KIND)
    assert envelopes.exists()
    assert {(e.feature, e.event, e.audience) for e in envelopes} == {
        ("hardware_requests", "maintenance_overdue", "staff")}
    assert w.im.pk in set(envelopes.values_list("recipient_id", flat=True))
    room = schedule(w, date(2020, 1, 10), "bookable_space", w.room)
    subject_reminders.notify(room, "due_soon")
    assert NotificationEnvelope.objects.filter(source_id=room.pk, source_kind=subject_reminders.KIND,
                                               feature="bookings", event="maintenance_due_soon").exists()

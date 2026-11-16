from datetime import timedelta
from unittest.mock import Mock

import pytest
from django.utils import timezone

from apps.events.models import Event, EventCheckInEvent, EventRegistration
from apps.events.services_checkin import mark_attended_with_event
from apps.integrations.models_contract import NotificationEnvelope
from apps.integrations.notification_sources import source_eligible
from apps.presence import services
from apps.presence.display import tv_payload
from apps.presence.event_attendance import event_attendance
from apps.presence.models import PresenceSession, PresenceSettings
from apps.presence.tasks import sweep_presence

pytestmark = pytest.mark.django_db


def ticket(lane, *, source="qr", reported_age=0, account=True):
    now = timezone.now()
    event = Event.objects.create(makerspace=lane.space, title="Public workshop", status="published", is_public=True,
        starts_at=now - timedelta(hours=1), ends_at=now + timedelta(hours=2), created_by=lane.staff)
    registration = EventRegistration.objects.create(event=event, member=lane.owner if account else None,
        name="Ticket holder", email="ticket@example.test", status="attended")
    checkin = EventCheckInEvent.objects.create(makerspace=lane.space, event=event, registration=registration,
        source=source, attended_at=now - timedelta(minutes=reported_age), actor=lane.staff)
    return event, registration, checkin


def due_session(lane):
    row = services.start_session(lane.owner, lane.space, 60, latitude=0, longitude=0)
    now = timezone.now()
    PresenceSession.objects.filter(pk=row.pk).update(started_at=now - timedelta(minutes=61), expires_at=now - timedelta(minutes=1))
    row.refresh_from_db()
    return row


def test_live_event_hook_idempotent_and_public_title(lane):
    event, registration, _ = ticket(lane)
    first, second = event_attendance(registration), event_attendance(registration)
    assert first and first.pk == second.pk
    assert first.status == "attending_event" and first.event_registration_id == registration.pk
    assert first.expires_at <= event.ends_at
    assert tv_payload(lane.space)[0]["event_title"] == event.title
    version = PresenceSettings.objects.get(makerspace=lane.space).display_version
    event.is_public = False
    event.save(update_fields=["is_public"])
    assert PresenceSettings.objects.get(makerspace=lane.space).display_version != version
    assert "event_title" not in tv_payload(lane.space)[0]


@pytest.mark.parametrize("source", ["online", "offline_sync"])
def test_staff_marks_and_offline_replay_never_create_current_presence(lane, source):
    _, registration, _ = ticket(lane, source=source)
    assert event_attendance(registration) is None
    assert not PresenceSession.objects.exists()


def test_historical_ticket_refused_even_if_recorded_now(lane):
    _, registration, _ = ticket(lane, reported_age=120)
    assert event_attendance(registration) is None
    assert not PresenceSession.objects.exists()


def test_delayed_live_ticket_and_corrected_attendance_refused(lane, monkeypatch):
    _, registration, checkin = ticket(lane)
    monkeypatch.setattr("apps.presence.event_attendance.timezone.now", lambda: checkin.recorded_at + timedelta(minutes=2))
    assert event_attendance(registration) is None
    EventRegistration.objects.filter(pk=registration.pk).update(status="registered")
    assert event_attendance(registration) is None
    assert not PresenceSession.objects.exists()


def test_unlinked_ticket_identity_not_inferred_from_contact(lane):
    _, registration, _ = ticket(lane, account=False)
    assert event_attendance(registration) is None


def test_event_hook_optional_when_disabled_tombstoned_or_failed(lane, monkeypatch):
    _, registration, _ = ticket(lane)
    lane.space.enabled_modules.remove("presence")
    lane.space.save(update_fields=["enabled_modules"])
    assert event_attendance(registration) is None
    lane.space.enabled_modules.append("presence")
    lane.space.save(update_fields=["enabled_modules"])
    monkeypatch.setattr("apps.presence.policy.app_is_tombstoned", lambda *_: True)
    assert event_attendance(registration) is None
    assert not PresenceSession.objects.exists()


def test_event_callback_runs_only_after_commit(lane, django_capture_on_commit_callbacks, monkeypatch):
    event, registration, _ = ticket(lane, source="online")
    EventRegistration.objects.filter(pk=registration.pk).update(status="registered")
    registration.refresh_from_db()
    bridge = Mock()
    monkeypatch.setattr("apps.presence.event_attendance.event_attendance", bridge)
    with django_capture_on_commit_callbacks(execute=True):
        updated, _ = mark_attended_with_event(registration, actor=lane.staff, source="qr")
        assert updated.status == "attended"
        assert bridge.call_count == 0
    assert bridge.call_count == 1


def test_historical_callback_never_scheduled(lane, django_capture_on_commit_callbacks, monkeypatch):
    _, registration, _ = ticket(lane, source="online")
    EventRegistration.objects.filter(pk=registration.pk).update(status="registered")
    registration.refresh_from_db()
    bridge = Mock()
    monkeypatch.setattr("apps.presence.event_attendance.event_attendance", bridge)
    with django_capture_on_commit_callbacks(execute=True):
        mark_attended_with_event(registration, actor=lane.staff, source="qr", attended_at=timezone.now() - timedelta(hours=1))
    bridge.assert_not_called()


def test_expiry_ends_session_and_emits_one_revision_bound_envelope(lane):
    row = due_session(lane)
    before = PresenceSettings.objects.get(makerspace=lane.space).display_version
    result = sweep_presence()
    row.refresh_from_db()
    assert result["expired"] == result["reminded"] == 1
    assert row.ended_at == row.expires_at and row.end_reason == "expired"
    assert PresenceSettings.objects.get(makerspace=lane.space).display_version != before
    envelope = NotificationEnvelope.objects.get(source_kind="presence.expiry")
    assert envelope.recipient_id == lane.owner.pk
    assert envelope.audience == "member" and envelope.feature == "presence"
    assert envelope.revision == str(row.revision) and source_eligible(envelope)
    assert tv_payload(lane.space) == []
    assert sweep_presence()["reminded"] == 0
    assert NotificationEnvelope.objects.filter(source_kind="presence.expiry").count() == 1


def test_reminder_selection_is_web_and_push_without_email_or_rooms(lane):
    from apps.integrations.notification_resolution import selected_policy
    due_session(lane)
    sweep_presence()
    envelope = NotificationEnvelope.objects.get(source_kind="presence.expiry")
    channels, fallback = selected_policy(envelope)
    assert channels == ["in_app", "native_push"] and fallback is False


def test_reminder_can_deliver_to_web_inbox(lane):
    from apps.integrations.notification_tasks import deliver_envelope
    from apps.notifications.models_inbox import NotificationInboxRow
    due_session(lane)
    sweep_presence()
    envelope = NotificationEnvelope.objects.get(source_kind="presence.expiry")
    deliver_envelope(envelope.pk)
    row = NotificationInboxRow.objects.get(makerspace=lane.space, user=lane.owner, feature="presence")
    assert "expired" in row.title.lower()
    assert not NotificationInboxRow.objects.filter(user=lane.staff, feature="presence").exists()


def test_expiry_preserves_existing_channel_opt_out(lane):
    from apps.notifications.models_preferences import NotificationPreference
    from apps.integrations.notification_resolution import resolve
    NotificationPreference.objects.create(makerspace=lane.space, user=lane.owner,
        category="presence", channels=[], email_fallback=False)
    due_session(lane)
    sweep_presence()
    envelope = NotificationEnvelope.objects.get(source_kind="presence.expiry")
    assert resolve(envelope) == []


def test_renew_after_expiry_invalidates_old_envelope(lane):
    row = due_session(lane)
    sweep_presence()
    envelope = NotificationEnvelope.objects.get(source_kind="presence.expiry")
    renewed = services.renew_session(lane.owner, lane.space, 120)
    assert renewed.pk == row.pk and renewed.ended_at is None
    assert not source_eligible(envelope)


def test_outbox_failure_still_expires_and_retries_reminder(lane, monkeypatch):
    from apps.presence import tasks
    row = due_session(lane)
    original = tasks.remind
    def unavailable(*args, **kwargs):
        raise RuntimeError("Outbox unavailable")
    monkeypatch.setattr("apps.presence.tasks.remind", unavailable)
    assert sweep_presence()["failed"] == 1
    row.refresh_from_db()
    assert row.end_reason == "expired" and row.expiry_reminded_at is None
    monkeypatch.setattr("apps.presence.tasks.remind", original)
    assert sweep_presence()["reminded"] == 1


def test_source_gate_and_module_off_skip_task(lane):
    from apps.tenant_migration.models_source_gate import SourceMigrationGate
    row = due_session(lane)
    gate = SourceMigrationGate.objects.create(makerspace=lane.space, state="draining",
        owner_id=SourceMigrationGate.new_owner_id(), heartbeat_at=timezone.now(),
        lease_expires_at=timezone.now() + timedelta(minutes=10))
    assert sweep_presence()["skipped"] == 1
    row.refresh_from_db()
    assert row.ended_at is None
    gate.delete()
    lane.space.enabled_modules.remove("presence")
    lane.space.save(update_fields=["enabled_modules"])
    assert sweep_presence()["expired"] == 0


def test_live_presence_is_drop_on_tenant_import(lane):
    from apps.tenant_migration.tenant_dump_model_catalog import FIRST_PARTY_MODEL_RULES
    from apps.tenant_migration.tenant_dump_types import ModelDisposition
    for label in ("presence.PresenceSession", "presence.PresenceSettings", "presence.PresencePreference"):
        assert FIRST_PARTY_MODEL_RULES[label].disposition == ModelDisposition.DROP


def test_both_schedulers_have_same_minute_cadence():
    from apps.presence.schedule import SCHEDULED_ENTRY, beat_entries
    entry = beat_entries([])["presence-expiry"]
    assert entry["task"] == SCHEDULED_ENTRY[1]
    assert entry["schedule"] == SCHEDULED_ENTRY[2] * 60
    assert beat_entries(["presence"]) == {}


@pytest.mark.parametrize("presence_on", [True, False])
def test_live_qr_check_in_end_to_end_and_events_survive_presence_off(lane, django_capture_on_commit_callbacks,
                                                                      presence_on):
    now = timezone.now()
    event = Event.objects.create(makerspace=lane.space, title="Live workshop", status="published", is_public=True,
        starts_at=now - timedelta(hours=1), ends_at=now + timedelta(hours=2), created_by=lane.staff)
    registration = EventRegistration.objects.create(event=event, member=lane.owner, name="Ticket holder",
        email="ticket@example.test", status="registered")
    if not presence_on:
        lane.space.enabled_modules.remove("presence")
        lane.space.save(update_fields=["enabled_modules"])
    with django_capture_on_commit_callbacks(execute=True):
        updated, _ = mark_attended_with_event(registration, actor=lane.staff, source="qr")
    assert updated.status == "attended"
    sessions = PresenceSession.objects.filter(event_registration=registration)
    assert sessions.count() == (1 if presence_on else 0)
    if presence_on:
        assert sessions.get().status == "attending_event"

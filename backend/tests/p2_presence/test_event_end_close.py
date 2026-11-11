"""P2-5: an event check-in's presence closes at the event's end through the minute sweeper."""
from datetime import timedelta

import pytest
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.events.models import Event
from apps.integrations.models_contract import NotificationEnvelope
from apps.presence import services
from apps.presence.event_attendance import event_attendance
from apps.presence.models import PresenceSession
from apps.presence.tasks import sweep_presence
from tests.p2_presence.test_events_tasks import due_session, ticket

pytestmark = pytest.mark.django_db


def event_session(lane):
    event, registration, _ = ticket(lane)
    row = event_attendance(registration)
    assert row is not None and row.event_registration_id == registration.pk
    return event, row


def expired_audits(row):
    return AuditLog.objects.filter(action="presence.expired", target_id=str(row.pk))


def test_event_shortened_after_check_in_closes_session_at_the_new_end(lane):
    event, row = event_session(lane)
    now = timezone.now()
    PresenceSession.objects.filter(pk=row.pk).update(started_at=now - timedelta(minutes=30))
    Event.objects.filter(pk=event.pk).update(ends_at=now - timedelta(minutes=5))
    event.refresh_from_db()
    assert sweep_presence()["expired"] == 1
    row.refresh_from_db()
    assert row.end_reason == "expired" and row.ended_at == event.ends_at and row.ended_by is None
    assert expired_audits(row).get().meta.get("cause") == "event_ended"
    # Renewal is refused once the event is over, so the member is never prompted for it.
    assert not NotificationEnvelope.objects.filter(source_kind="presence.expiry").exists()
    assert AuditLog.objects.filter(action="presence.expiry_reminder_skipped", target_id=str(row.pk)).count() == 1
    assert sweep_presence()["expired"] == 0


def test_end_is_never_before_the_check_in(lane):
    event, row = event_session(lane)
    Event.objects.filter(pk=event.pk).update(ends_at=event.starts_at + timedelta(minutes=1))
    sweep_presence()
    row.refresh_from_db()
    assert row.ended_at == row.started_at


def test_natural_event_end_expiry_closes_without_renewal_prompt(lane):
    event, row = event_session(lane)
    now = timezone.now()
    PresenceSession.objects.filter(pk=row.pk).update(started_at=now - timedelta(hours=2),
                                                     expires_at=now - timedelta(minutes=1))
    Event.objects.filter(pk=event.pk).update(ends_at=now - timedelta(minutes=1))
    assert sweep_presence()["expired"] == 1
    row.refresh_from_db()
    assert row.ended_at == row.expires_at
    assert expired_audits(row).get().meta.get("cause") == "event_ended"
    assert not NotificationEnvelope.objects.filter(source_kind="presence.expiry").exists()


def test_running_event_session_stays_open(lane):
    _, row = event_session(lane)
    assert sweep_presence()["expired"] == 0
    row.refresh_from_db()
    assert row.ended_at is None


def test_event_longer_than_presets_still_expires_and_prompts_renewal(lane):
    _, row = event_session(lane)
    now = timezone.now()
    PresenceSession.objects.filter(pk=row.pk).update(started_at=now - timedelta(minutes=61),
                                                     expires_at=now - timedelta(minutes=1))
    assert sweep_presence()["expired"] == 1
    row.refresh_from_db()
    assert row.ended_at == row.expires_at and "cause" not in expired_audits(row).get().meta
    assert NotificationEnvelope.objects.filter(source_kind="presence.expiry").count() == 1


def test_manual_check_ins_close_exactly_as_before(lane):
    running = services.staff_check_in(lane.staff, lane.owner, lane.space, 60)
    assert sweep_presence()["expired"] == 0
    running.refresh_from_db()
    assert running.ended_at is None
    row = due_session(lane)
    result = sweep_presence()
    row.refresh_from_db()
    assert result["expired"] == result["reminded"] == 1
    assert row.ended_at == row.expires_at and "cause" not in expired_audits(row).get().meta

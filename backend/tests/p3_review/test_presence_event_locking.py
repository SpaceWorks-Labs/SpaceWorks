from datetime import timedelta

import pytest
from django.db import connection, transaction
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from apps.events.models import Event, EventRegistration
from apps.events.services_checkin import mark_attended_with_event
from apps.presence.event_attendance import event_attendance
from apps.presence.models import PresenceSession

pytestmark = pytest.mark.django_db


def test_hook_inside_checkin_transaction_locks_event_before_presence_tenant(lane):
    now = timezone.now()
    event = Event.objects.create(makerspace=lane.space, title="Live workshop", status="published",
        starts_at=now - timedelta(hours=1), ends_at=now + timedelta(hours=1))
    registration = EventRegistration.objects.create(event=event, member=lane.owner,
        name="Owner", email=lane.owner.email, status="registered")
    # Credential material is prepared BEFORE domain locks (apps/events/credentials/preparation.py), so the
    # check-in service refuses a caller-held transaction; run it at the top level and exercise the
    # presence hook (which a real check-in runs on commit) inside its own transaction.
    updated, _ = mark_attended_with_event(registration, actor=lane.staff, source="qr")
    with transaction.atomic():
        # Exercise the real hook while a transaction is open.
        with CaptureQueriesContext(connection) as queries:
            session = event_attendance(updated)
        assert session is not None
        assert session.event_registration_id == registration.pk
        assert session.status == "attending_event"
        assert event_attendance(updated).pk == session.pk
    locks = [query["sql"] for query in queries if "FOR UPDATE" in query["sql"]
             or "FOR NO KEY UPDATE" in query["sql"]]
    assert 'FROM "events_event"' in locks[0]
    assert 'FOR UPDATE OF "events_event", "makerspaces_makerspace"' in locks[0]
    assert PresenceSession.objects.filter(event_registration=registration).count() == 1


def test_checkin_commit_callback_creates_presence(lane, django_capture_on_commit_callbacks):
    now = timezone.now()
    event = Event.objects.create(makerspace=lane.space, title="Live workshop", status="published",
        starts_at=now - timedelta(hours=1), ends_at=now + timedelta(hours=1))
    registration = EventRegistration.objects.create(event=event, member=lane.owner,
        name="Owner", email=lane.owner.email, status="registered")
    with django_capture_on_commit_callbacks(execute=True):
        mark_attended_with_event(registration, actor=lane.staff, source="qr")
        assert not PresenceSession.objects.filter(event_registration=registration).exists()
    assert PresenceSession.objects.get(event_registration=registration).status == "attending_event"

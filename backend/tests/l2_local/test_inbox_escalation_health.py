"""X38: inbox snooze/archive, escalation re-ping, dead chat rooms switched off (on and off)."""
from datetime import timedelta
from uuid import uuid4

import pytest
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.integrations import destination_health
from apps.integrations.models_destinations import NotificationDestination
from apps.integrations.models_notifications import NotificationDeliveryLog
from apps.notifications import escalation
from apps.notifications.models_browser_alerts import NotificationEscalation
from apps.notifications.models_inbox import NotificationInboxRow
from tests.accounts.account_factories import make_staff as make_person_staff
from tests.events.collab_helpers import client_for
from tests.events.ticketing_helpers import event_space
from tests.l2_local.helpers import off, on

pytestmark = pytest.mark.django_db


def space_with_staff(slug):
    space = event_space(slug)
    space.enabled_modules = sorted(set(space.enabled_modules) | {"notifications"})
    space.save(update_fields=["enabled_modules"])
    # One account per person (U-A1): a person holding a staff-track Space Manager row.
    return space, make_person_staff(space, username=f"staff-{slug}", email=f"staff-{slug}@example.test")


def inbox_row(space, user, **values):
    return NotificationInboxRow.objects.create(makerspace=space, user=user, feature="hardware_requests",
                                               event="submitted", event_key=uuid4(), title="New request",
                                               audience="staff", **values)


def test_snooze_and_archive_hide_rows_only_while_on_and_restore_brings_them_back():
    space, staff = space_with_staff("inbox-snooze")
    row = inbox_row(space, staff)
    base = f"/api/v1/notifications/inbox/{space.pk}"
    until = (timezone.now() + timedelta(hours=2)).isoformat()
    assert client_for(staff).post(f"{base}/{row.pk}/snooze", {"until": until}, format="json").status_code == 404
    on(space, "notifications.inbox_snooze")
    assert client_for(staff).post(f"{base}/{row.pk}/snooze", {"until": until}, format="json").status_code == 200
    assert client_for(staff).get(base).json()["count"] == 0
    assert client_for(staff).get(f"{base}/unread-count").json() == {"count": 0}
    off(space, "notifications.inbox_snooze")
    assert client_for(staff).get(base).json()["count"] == 1  # data kept, simply shown again
    on(space, "notifications.inbox_snooze")
    assert client_for(staff).post(f"{base}/{row.pk}/archive").status_code == 200
    assert client_for(staff).get(f"{base}?archived=true").json()["count"] == 1
    assert client_for(staff).post(f"{base}/{row.pk}/restore").status_code == 200
    assert client_for(staff).get(base).json()["count"] == 1
    assert AuditLog.objects.filter(action="notification.inbox_archived").exists()


def test_unseen_urgent_notice_escalates_once_with_no_message_text(monkeypatch):
    space, staff = space_with_staff("escalate")
    room = NotificationDestination.objects.create(makerspace=space, channel="telegram", label="Desk",
                                                  telegram_chat_id="-1")
    posts = []
    monkeypatch.setattr("apps.integrations.dispatch_destination.deliver_text_to_destination",
                        lambda space, destination, **kw: posts.append(kw["text"]) or (True, ""))
    row = inbox_row(space, staff)
    NotificationInboxRow.objects.filter(pk=row.pk).update(created_at=timezone.now() - timedelta(minutes=40))
    off(space, "notifications.escalation")
    assert escalation.escalate_unseen_task()["escalated"] == 0
    on(space, "notifications.escalation")
    assert escalation.escalate_unseen_task()["escalated"] == 1
    assert escalation.escalate_unseen_task()["escalated"] == 0
    assert NotificationEscalation.objects.get().rooms_posted == 1 and room.is_active
    assert "New request" not in posts[0]


def test_a_read_notice_never_escalates():
    space, staff = space_with_staff("escalate-read")
    on(space, "notifications.escalation")
    row = inbox_row(space, staff, read_at=timezone.now())
    NotificationInboxRow.objects.filter(pk=row.pk).update(created_at=timezone.now() - timedelta(minutes=40))
    assert escalation.unseen_keys(space, timezone.now()) == []


def test_five_failures_in_a_row_switch_a_room_off_and_tell_staff(django_capture_on_commit_callbacks):
    space, _staff = space_with_staff("dead-room")
    room = NotificationDestination.objects.create(makerspace=space, channel="telegram", label="Old room",
                                                  telegram_chat_id="-9")
    for status in ("failed",) * 4:
        NotificationDeliveryLog.objects.create(makerspace=space, channel="telegram", destination=room,
                                               feature="hardware_requests", event="submitted", text_body="x",
                                               status=status)
    assert not destination_health.dead(room)
    NotificationDeliveryLog.objects.create(makerspace=space, channel="telegram", destination=room,
                                           feature="hardware_requests", event="submitted", text_body="x",
                                           status="failed")
    with django_capture_on_commit_callbacks(execute=True):
        assert destination_health.disable_dead_destinations_task()["disabled"] == 1
    room.refresh_from_db()
    assert not room.is_active
    assert AuditLog.objects.filter(action="notification.destination_auto_disabled").exists()
    from apps.notifications.models import Notification
    assert Notification.objects.filter(makerspace=space, event="destination_auto_disabled").exists()

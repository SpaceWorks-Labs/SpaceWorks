"""#185 item 4: archive on a date, purge after the grace period, reminders, cancellable."""

from datetime import timedelta

import pytest
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.makerspaces.models import Makerspace
from apps.space_controls.models import SpaceControlState
from apps.space_controls.schedule_mail import due_reminder
from apps.space_controls.services_schedule import is_archived
from apps.space_controls.tasks import run_schedules

from .helpers import api, control, manager, space, superadmin

pytestmark = pytest.mark.django_db


@pytest.fixture
def world(mailbox):
    lab = space()
    root, boss = superadmin(), manager(lab)
    return type("World", (), dict(lab=lab, root=root, boss=boss, mail=mailbox))


def schedule(world, days=10, grace=90):
    archive_on = timezone.now() + timedelta(days=days)
    response = control(world.root, world.lab, "schedule",
                       {"archive_on": archive_on.isoformat(), "purge_grace_days": grace, "note": "Closing"})
    assert response.status_code == 200, response.content
    return archive_on


def state(world):
    return SpaceControlState.objects.get(makerspace=world.lab)


def test_full_timeline(world, django_capture_on_commit_callbacks):
    archive_on = schedule(world, days=10, grace=30)
    assert api(world.root).get(f"/api/v1/admin/platform/space-health/{world.lab.pk}").json()["state"] == "scheduled"
    with django_capture_on_commit_callbacks(execute=True):
        assert run_schedules(timezone.now())["archived"] == 0
    assert state(world).reminders_sent == []  # 10 days out: no archive reminder yet (7 and 1)

    with django_capture_on_commit_callbacks(execute=True):
        run_schedules(archive_on - timedelta(days=6, hours=12))
    assert state(world).reminders_sent == ["archive:7"]
    assert "will be archived in 7 days" in world.mail[-1].subject

    with django_capture_on_commit_callbacks(execute=True):
        assert run_schedules(archive_on + timedelta(minutes=1))["archived"] == 1
    world.lab.refresh_from_db()
    assert is_archived(world.lab)
    after = state(world)
    assert after.archive_on is None and after.purge_due_at is not None
    assert AuditLog.objects.filter(action="space_control.scheduled_archive_ran").exists()
    assert AuditLog.objects.filter(action="makerspace.archived", makerspace=world.lab).exists()

    with django_capture_on_commit_callbacks(execute=True):
        run_schedules(after.purge_due_at - timedelta(days=29, hours=12))
    assert state(world).reminders_sent == ["purge:30"]
    with django_capture_on_commit_callbacks(execute=True):
        run_schedules(after.purge_due_at - timedelta(hours=12))
    assert state(world).reminders_sent == ["purge:30", "purge:7", "purge:1"]  # one mail, both marked

    with django_capture_on_commit_callbacks(execute=True):
        assert run_schedules(after.purge_due_at + timedelta(minutes=1))["purged"] == 1
    assert not Makerspace.objects.filter(pk=world.lab.pk).exists()
    assert AuditLog.objects.filter(action="space_control.scheduled_purge_ran").exists()


def test_reminder_thresholds_collapse_into_one_mail():
    row = SpaceControlState(purge_due_at=timezone.now() + timedelta(days=3), reminders_sent=[])
    assert due_reminder(row) == ("purge", 3, ["purge:30", "purge:7"])


def test_cancel_stops_the_schedule(world):
    archive_on = schedule(world)
    assert control(world.root, world.lab, "schedule/cancel").json()["state"] == "active"
    run_schedules(archive_on + timedelta(days=1))
    world.lab.refresh_from_db()
    assert not is_archived(world.lab)
    assert control(world.root, world.lab, "schedule/cancel").json()["code"] == "no_schedule"
    assert AuditLog.objects.filter(action="space_control.schedule_cancelled").exists()


def test_archived_space_schedules_only_its_purge(world):
    assert control(world.root, world.lab, "archive").status_code == 200
    bad = control(world.root, world.lab, "schedule", {"archive_on": timezone.now().isoformat(), "purge_grace_days": 5})
    assert bad.status_code == 400
    response = control(world.root, world.lab, "schedule", {"purge_grace_days": 5})
    assert response.status_code == 200 and response.json()["schedule"]["purge_due_at"]
    assert control(world.root, world.lab, "schedule", {"purge_grace_days": 5}).json()["code"] == "schedule_exists"
    # Unarchiving clears the purge that no longer applies.
    assert control(world.root, world.lab, "unarchive").json()["schedule"] is None


def test_purge_is_held_when_the_scheduler_is_no_longer_a_superadmin(world):
    control(world.root, world.lab, "archive")
    control(world.root, world.lab, "schedule", {"purge_grace_days": 1})
    # Decision 63 account split: user_platform_flags forbids a platform account without is_superuser, so
    # the scheduler stops being an ACTIVE superadmin by being deactivated instead.
    world.root.is_active = False
    world.root.save(update_fields=["is_active"])
    due = state(world).purge_due_at + timedelta(minutes=1)
    assert run_schedules(due)["purged"] == 0
    assert run_schedules(due)["purged"] == 0
    assert Makerspace.objects.filter(pk=world.lab.pk).exists()
    assert AuditLog.objects.filter(action="space_control.schedule_blocked").count() == 1


def test_schedule_validation(world):
    past = (timezone.now() - timedelta(days=1)).isoformat()
    assert control(world.root, world.lab, "schedule", {"archive_on": past}).status_code == 400
    assert control(world.root, world.lab, "schedule", {"archive_on": None}).status_code == 400
    assert control(world.boss, world.lab, "schedule", {}).status_code == 403


def test_purge_from_the_console_needs_the_slug(world):
    control(world.root, world.lab, "archive")
    assert control(world.root, world.lab, "purge", {"confirm_slug": "wrong"}).status_code == 400
    assert control(world.root, world.lab, "purge", {"confirm_slug": world.lab.slug}).status_code == 204
    assert not Makerspace.objects.filter(pk=world.lab.pk).exists()

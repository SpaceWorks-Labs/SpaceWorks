from django.conf import settings

from apps.events.tasks_programme import sweep_admission_deadlines_task
import pytest


def test_admission_sweep_is_scheduled_and_registered():
    from apps.events import tasks
    assert tasks.sweep_admission_deadlines_task is sweep_admission_deadlines_task
    entry = settings.CELERY_BEAT_SCHEDULE["event-admission-deadlines"]
    assert entry["task"] == "apps.events.tasks_programme.sweep_admission_deadlines_task"


# Task dispatch checks the deployment-mode binding in the database (cloud lane).
@pytest.mark.django_db
def test_tombstone_sweep_has_no_side_effects(monkeypatch):
    monkeypatch.setattr("apps.events.tasks_programme.runtime_active", lambda _: False)
    assert sweep_admission_deadlines_task() == 0


# Task dispatch checks the deployment-mode binding in the database (cloud lane).
@pytest.mark.django_db
def test_contributor_sweep_schedule_and_tombstone(monkeypatch):
    from apps.events.tasks_contributions import sweep_contributor_maintenance_task
    from apps.events import tasks
    assert tasks.sweep_contributor_maintenance_task is sweep_contributor_maintenance_task
    assert settings.CELERY_BEAT_SCHEDULE["event-contributor-maintenance"]["task"] == sweep_contributor_maintenance_task.name
    monkeypatch.setattr("apps.events.tasks_contributions.runtime_active", lambda _: False)
    assert sweep_contributor_maintenance_task() == {"processed": 0, "skipped": 0, "failed": 0}


from tests.events.programme.admission.test_support import world, submitted


@pytest.mark.django_db(transaction=True)
def test_due_offer_expires_once_and_repeated_sweep_is_idempotent(world):
    from datetime import timedelta
    from django.utils import timezone
    from apps.events.hackathons.admission_maintenance import expire_due

    application = submitted(world)
    application.rsvp_due_at = timezone.now() - timedelta(seconds=1)
    application.save(update_fields=["rsvp_due_at"])
    assert expire_due(event_id=world.event.pk) == 1
    application.refresh_from_db()
    assert application.state == "expired"
    calls, notices = list(world.bridge.calls), list(world.notices)
    assert expire_due(event_id=world.event.pk) == 0
    assert world.bridge.calls == calls
    assert world.notices == notices

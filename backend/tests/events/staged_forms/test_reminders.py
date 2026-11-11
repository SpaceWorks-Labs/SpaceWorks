"""Due revisions and scheduled tombstones prevent stale and starved reminders."""
from datetime import timedelta
from types import SimpleNamespace
from uuid import uuid4
import pytest
from django.utils import timezone
from apps.events.staged_forms import reminders, rsvp_reminders
from apps.events.staged_forms.assignment_workflow import manage
from apps.events.staged_forms.stage_workflow import activate_locked
from apps.events.staged_forms.trigger_service import Participant
from apps.operations.reminder_services import schedule_reminders
from .conftest import definition, participant
from .test_inline_submission import outer

pytestmark = pytest.mark.django_db(transaction=True)


def test_extension_invalidates_old_due_identity_and_discovery_progresses(stage_env):
    env = stage_env
    registration, application = participant(env)
    rows = [definition(env, key=f"remind-{i}", due_after_seconds=3*86400) for i in range(2)]
    with outer(env) as (event, locks):
        assignments = [activate_locked(definition=row, subject=Participant(event, env.owner.pk, registration, application), locks=locks) for row in rows]
    now = timezone.now()
    first = list(reminders.discover(env.space, now, 1, None))
    assert len(first) == 1
    subject = first[0]
    schedule_reminders(makerspace=env.space, source="stage_forms", subject=subject.subject, kind=subject.kind,
        due_at=subject.due_at, offsets=subject.offsets)
    second = list(reminders.discover(env.space, now, 1, None))
    assert len(second) == 1 and second[0].subject != first[0].subject
    assignment = assignments[0]
    schedule = SimpleNamespace(subject=reminders.identity(assignment), due_at=assignment.effective_due_at, offset_seconds=-86400)
    assert reminders.resolve(env.space, schedule, now) is not None
    manage(event_id=env.event.pk, actor=env.manager, assignment_id=assignment.pk, action="extend", data={
        "operation_id": uuid4(), "expected_version": assignment.version, "expected_response_version": assignment.response.version,
        "expected_stage_form_version": rows[0].version, "due_at": assignment.effective_due_at + timedelta(days=1),
        "confirmed": True, "reason_code": "extension", "reason": "Reviewed extension"})
    assert reminders.resolve(env.space, schedule, now) is None


@pytest.mark.parametrize("stage_env", ["hackathon"], indirect=True)
def test_rsvp_extension_uses_utc_Z_and_invalidates_old_schedule(stage_env):
    env = stage_env
    _, application = participant(env)
    application.state, application.offered_at, application.rsvp_due_at = "offered", env.now, env.now + timedelta(hours=20)
    application.decision_revision = 3
    application.save()
    found = list(rsvp_reminders.discover(env.space, env.now, 10, None))
    assert len(found) == 1 and found[0].subject.endswith("Z")
    schedule = SimpleNamespace(subject=found[0].subject, due_at=found[0].due_at, offset_seconds=-86400)
    assert rsvp_reminders.resolve(env.space, schedule, env.now) is not None
    application.rsvp_due_at += timedelta(hours=2)
    application.save(update_fields=["rsvp_due_at"])
    assert rsvp_reminders.resolve(env.space, schedule, env.now) is None


def test_cancelled_events_cannot_build_or_dispatch_reminders(stage_env):
    env = stage_env
    registration, application = participant(env)
    row = definition(env, due_after_seconds=3*86400)
    with outer(env) as (event, locks):
        assignment = activate_locked(definition=row, subject=Participant(event, env.owner.pk, registration, application), locks=locks)
    schedule = SimpleNamespace(subject=reminders.identity(assignment), due_at=assignment.effective_due_at, offset_seconds=-86400)
    env.event.status = "cancelled"
    env.event.save(update_fields=["status"])
    assert reminders.build(env.space, schedule, env.now, None) is None

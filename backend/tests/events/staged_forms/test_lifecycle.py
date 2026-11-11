"""Cancellation, next-stage locks and rescheduling never write admission state."""
from datetime import timedelta
from uuid import uuid4
import pytest
from django.db import transaction
from apps.events.contracts.providers import LockedContext
from apps.events.programme_locks import fences
from apps.events.staged_forms.stage_workflow import activate_locked, reconcile_deadlines_locked
from apps.events.staged_forms.lifecycle import cancel_participant_locked, reschedule_event_locked
from apps.events.staged_forms.trigger_service import Participant, applicable
from apps.events.staged_forms.response_models import StageFormResponse
from apps.events.staged_forms.guards import readiness
from .conftest import definition, participant
from .test_inline_submission import outer

pytestmark = pytest.mark.django_db(transaction=True)


def test_scheduled_assignment_opens_then_overdue_without_cancelling_registration(stage_env):
    env = stage_env
    registration, application = participant(env)
    row = definition(env, opening_mode="absolute", opens_at=env.now + timedelta(hours=1), due_after_seconds=7200)
    subject = Participant(env.event, env.owner.pk, registration, application)
    with outer(env) as (event, locks):
        assignment = activate_locked(definition=row, subject=subject, locks=locks)
        assert assignment.state == "scheduled"
        reconcile_deadlines_locked(event=event, now=env.now + timedelta(hours=1, minutes=1), locks=locks)
        assignment.refresh_from_db()
        assert assignment.state == "open"
        reconcile_deadlines_locked(event=event, now=env.now + timedelta(hours=3), locks=locks)
    assignment.refresh_from_db()
    registration.refresh_from_db()
    assert assignment.state == "overdue"
    assert registration.status == "registered"


def test_cancelled_assignment_is_durable_exemption(stage_env):
    env = stage_env
    registration, application = participant(env)
    row = definition(env, required=True, missed_action="block", blocked_actions=["claim_submit"])
    subject = Participant(env.event, env.owner.pk, registration, application)
    with outer(env) as (event, locks):
        assignment = activate_locked(definition=row, subject=subject, locks=locks)
        assert not readiness(subject, "claim_submit")["ready"]
        cancel_participant_locked(subject=subject, locks=locks)
        assert activate_locked(definition=row, subject=subject, locks=locks).pk == assignment.pk
    assert readiness(subject, "claim_submit")["ready"]
    assert StageFormResponse.objects.get(assignment=assignment).state == "withdrawn"


def test_date_reschedule_preserves_reviewed_extension_and_absolute_deadline(stage_env):
    env = stage_env
    registration, application = participant(env)
    relative = definition(env, key="relative", opening_mode="event_start", opening_offset_seconds=-86400,
        due_mode="event_start", due_after_seconds=None, due_event_offset_seconds=86400)
    absolute = definition(env, key="absolute", due_mode="absolute", due_after_seconds=None, due_at=env.now + timedelta(days=4))
    subject = Participant(env.event, env.owner.pk, registration, application)
    with outer(env) as (event, locks):
        first = activate_locked(definition=relative, subject=subject, locks=locks)
        second = activate_locked(definition=absolute, subject=subject, locks=locks)
        first.effective_due_at += timedelta(hours=2)
        first.save()
        old = first.effective_due_at
        event.starts_at += timedelta(days=2)
        event.ends_at += timedelta(days=2)
        event.event_date_revision += 1
        event.save()
        reschedule_event_locked(event=event, locks=locks, actor=env.manager)
    first.refresh_from_db()
    second.refresh_from_db()
    assert first.effective_due_at == old + timedelta(days=2)
    assert second.effective_due_at == absolute.due_at
    assert first.due_revision == 2 and second.due_revision == 1


def test_next_stage_closes_response_without_another_stage_definition(stage_env):
    env = stage_env
    registration, application = participant(env)
    row = definition(env, lock_on_next_stage=True)
    if application:
        application.state, application.offered_at = "offered", env.now
        application.save()
    subject = Participant(env.event, env.owner.pk, registration, application)
    with outer(env) as (event, locks):
        assignment = activate_locked(definition=row, subject=subject, locks=locks)
        reconcile_deadlines_locked(event=event, now=env.now + timedelta(seconds=1), locks=locks)
    assignment.refresh_from_db()
    assert assignment.next_stage_locked_at is not None
    assert StageFormResponse.objects.get(assignment=assignment).state == "locked"
    # A reasoned reopen permits this already-reached milestone. A later one may
    # lock again; recovery must not immediately undo the manager's own command.
    from apps.events.staged_forms.assignment_workflow import manage
    response = StageFormResponse.objects.get(assignment=assignment)
    manage(event_id=env.event.pk, actor=env.manager, assignment_id=assignment.pk, action="reopen", data={
        "operation_id": uuid4(), "expected_version": assignment.version, "expected_response_version": response.version,
        "expected_stage_form_version": row.version, "confirmed": True, "reason_code": "recovery",
        "reason": "Permit the corrected form", "due_at": env.now + timedelta(days=2)})
    with outer(env) as (event, locks):
        reconcile_deadlines_locked(event=event, now=env.now + timedelta(minutes=1), locks=locks)
    assignment.refresh_from_db()
    assert assignment.next_stage_locked_at is None
    assert StageFormResponse.objects.get(assignment=assignment).state == "draft"

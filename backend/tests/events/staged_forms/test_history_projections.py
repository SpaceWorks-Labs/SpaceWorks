"""Organizer/finance history selects immutable evidence and intersects consent."""
from datetime import timedelta
import json
from uuid import uuid4
import pytest
from apps.audit.services import record
from apps.events.programme.form_models import EventFormRevision
from apps.events.staged_forms.stage_workflow import activate_locked
from apps.events.staged_forms.trigger_service import Participant
from apps.events.staged_forms.response_workflow import prepare, save
from apps.events.staged_forms.assignment_workflow import manage
from apps.events.staged_forms.projections import detail
from apps.events.staged_forms.response_models import StageFormResponse
from .conftest import definition, participant, payload
from .test_inline_submission import outer

pytestmark = pytest.mark.django_db(transaction=True)


def submitted(env):
    registration, application = participant(env)
    row = definition(env, questions=[
        {"id": "public", "type": "short_text", "label": "Public", "required": True},
        {"id": "private", "type": "long_text", "label": "Sensitive", "required": True, "sensitive": True}])
    with outer(env) as (event, locks):
        assignment = activate_locked(definition=row, subject=Participant(event, env.owner.pk, registration, application), locks=locks)
    response = assignment.response
    data = payload(row, answers={"public": "Organizer answer", "private": "Finance answer"}, operation_id=uuid4(),
        expected_version=response.version, expected_assignment_version=assignment.version)
    prepared = prepare(response=response, actor=env.owner, data=data, operation_id=data["operation_id"])
    save(event_id=env.event.pk, actor=env.owner, response_id=response.pk, data=data, prepared=prepared)
    return row, StageFormResponse.objects.get(pk=response.pk)


def test_disjoint_projections_never_list_sensitive_omission_ids(stage_env):
    env = stage_env
    row, response = submitted(env)
    organizer = detail(actor=env.manager, response=response)
    finance = detail(actor=env.manager, response=response, finance=True)
    assert [answer["id"] for answer in organizer["answers"]["answers"]] == ["public"]
    assert [answer["id"] for answer in finance["answers"]["answers"]] == ["private"]
    assert "private" not in organizer["omitted_question_ids"]
    assert "Finance answer" not in json.dumps(organizer, default=str)
    assert set(organizer["answer_review"]) == {"date_revision", "locked"}
    assert organizer["response_revision"] == 1


def test_cancel_reassign_retains_pointer_and_immutable_history(stage_env):
    env = stage_env
    row, response = submitted(env)
    assignment = response.assignment
    old_pointer = response.current_submitted_revision_id
    base = {"operation_id": uuid4(), "expected_version": assignment.version,
        "expected_response_version": response.version, "expected_stage_form_version": row.version,
        "reason_code": "no_longer_required", "reason": "Private staff reason", "confirmed": True}
    manage(event_id=env.event.pk, actor=env.manager, assignment_id=assignment.pk, data=base, action="cancel")
    assignment.refresh_from_db()
    response.refresh_from_db()
    assert assignment.state == "cancelled" and assignment.completed_response_id is None
    assert response.current_submitted_revision_id == old_pointer
    revision = EventFormRevision.objects.create(event=env.event, form_key="stage", selector_kind="stage", selector_id=row.pk,
        revision=2, schema={**row.current_revision.schema, "revision": 2})
    record(env.manager, "event.stage_form.published", makerspace=env.space, target=row,
           meta={"stage_form_id": row.pk, "revision_id": revision.pk})
    data = {**base, "operation_id": uuid4(), "expected_version": assignment.version, "expected_response_version": response.version,
        "replacement_form_revision_id": revision.pk, "due_at": env.now + timedelta(days=2)}
    manage(event_id=env.event.pk, actor=env.manager, assignment_id=assignment.pk, data=data, action="reassign")
    assignment.refresh_from_db()
    response.refresh_from_db()
    assert response.state == "draft" and response.current_submitted_revision_id == old_pointer
    assert response.submitted_revisions.count() == 1
    assert assignment.pinned_form_revision_id == revision.pk and assignment.completed_response_id is None
    assert detail(actor=env.manager, response=response, revision=1)["response_revision"] == 1

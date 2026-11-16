"""R bridge acceptance; G must additionally exercise its real outer endpoints."""
from contextlib import contextmanager
from copy import deepcopy
from uuid import uuid4
import pytest
from django.db import transaction
from apps.accounts.saved_details import subject_binding
from apps.accounts.saved_details.errors import SavedDetailsError
from apps.accounts.saved_details.models import SavedDetailUpdateIntent
from apps.events.models import Event, EventRegistration, EventCommandReceipt
from apps.events.contracts.providers import LockedContext
from apps.events.programme_locks import fences
from apps.events.staged_forms import prefill_provider
from apps.events.staged_forms.inline_submission import prepare_inline, validate_conflicts, bind_locked
from apps.events.staged_forms.response_models import StageFormAssignment, StageFormResponseRevision
from apps.events.staged_forms.transactions import command, replay_before_prepare
from .conftest import definition, participant, payload

pytestmark = pytest.mark.django_db(transaction=True)


@contextmanager
def outer(env):
    with transaction.atomic(), fences(tenant_ids=(env.space.pk,), account_ids=(env.owner.pk,)):
        event = Event.objects.select_for_update().get(pk=env.event.pk)
        yield event, LockedContext(event_id=event.pk, tenant_ids=(env.space.pk,), account_ids=(env.owner.pk,))


def test_virtual_children_bind_and_reverse_order_is_stable(stage_env):
    env, operation = stage_env, uuid4()
    rows = [definition(env, key=f"step-{i}") for i in range(2)]
    first = prepare_inline(event=env.event, actor=env.owner, outer_operation_id=operation, stage_forms=[payload(row) for row in rows])
    second = prepare_inline(event=env.event, actor=env.owner, outer_operation_id=operation, stage_forms=[payload(row) for row in reversed(rows)])
    assert [p.prepared.operation_id for p in first] == [p.prepared.operation_id for p in second]
    validate_conflicts(first)
    with outer(env) as (event, locks):
        registration, application = participant(env)
        result = bind_locked(event=event, actor=env.owner, registration=registration, application=application,
            prepared_stages=first, locks=locks)
    assert len(result["form_operations"]) == 2
    assert [status["state"] for status in result["form_save_intents"]] == ["not_requested"] * 2
    assert StageFormResponseRevision.objects.count() == 2
    assert set(StageFormAssignment.objects.values_list("registration_id", flat=True)) == {registration.pk}


@pytest.mark.parametrize("failure", ("final_bind", "receipt"))
def test_failure_rolls_back_every_stage_and_new_participation(stage_env, monkeypatch, failure):
    env = stage_env
    rows = [definition(env, key=f"step-{i}") for i in range(2)]
    prepared = prepare_inline(event=env.event, actor=env.owner, outer_operation_id=uuid4(), stage_forms=[payload(row) for row in rows])
    if failure == "final_bind":
        from apps.events.staged_forms import inline_submission
        original = inline_submission.submit_locked
        def fail(**kwargs):
            if kwargs["assignment"].stage_form_id == rows[-1].pk:
                raise RuntimeError("injected final bind failure")
            return original(**kwargs)
        monkeypatch.setattr(inline_submission, "submit_locked", fail)
    with pytest.raises(RuntimeError), outer(env) as (event, locks):
        registration, application = participant(env)
        bind_locked(event=event, actor=env.owner, registration=registration, application=application,
            prepared_stages=prepared, locks=locks)
        raise RuntimeError("injected final receipt failure")
    assert not EventRegistration.objects.filter(event=env.event).exists()
    assert not StageFormAssignment.objects.exists()
    assert not StageFormResponseRevision.objects.exists()
    assert not SavedDetailUpdateIntent.objects.exists()


def test_real_saved_intents_bind_under_pending_map_and_cross_form_conflicts(stage_env, monkeypatch):
    env = stage_env
    monkeypatch.setattr(subject_binding, "_provider", prefill_provider)
    rows = [definition(env, key=f"save-{i}", questions=[{"id": "name", "type": "short_text", "label": "Name",
        "required": True, "profile_field_key": "name"}]) for i in range(2)]
    forms = [payload(row, answers={"name": "Maker"}, save_choices={"name": True}, saved_detail_versions={"name": 0}) for row in rows]
    prepared = prepare_inline(event=env.event, actor=env.owner, outer_operation_id=uuid4(), stage_forms=forms)
    validate_conflicts(prepared)
    changed = deepcopy(forms)
    changed[-1]["answers"]["name"] = "Different"
    conflicting = prepare_inline(event=env.event, actor=env.owner, outer_operation_id=uuid4(), stage_forms=changed)
    with pytest.raises(SavedDetailsError) as exc:
        validate_conflicts(conflicting)
    assert str(exc.value.detail["code"]) == "saved_detail_form_conflict"
    with outer(env) as (event, locks):
        registration, application = participant(env)
        result = bind_locked(event=event, actor=env.owner, registration=registration, application=application,
            prepared_stages=prepared, locks=locks)
    assert SavedDetailUpdateIntent.objects.count() == 2
    assert all(value["state"] == "pending" for value in result["form_save_intents"])
    assert all(row.subject_kind == "stage_response" and row.subject_id for row in SavedDetailUpdateIntent.objects.all())


def test_response_replay_can_be_resolved_without_preparation(stage_env):
    env = stage_env
    participant(env)
    data = {"operation_id": uuid4(), "expected_version": 1}
    with command(event_id=env.event.pk, actor=env.owner, data=data, action="test.replay", owner=True) as ctx:
        reference = ctx.finish(ctx.event)
    assert replay_before_prepare(event=env.event, actor=env.owner, data=data, action="test.replay") == reference
    from apps.payments.event_payouts.errors import PayoutError
    with pytest.raises(PayoutError):
        replay_before_prepare(event=env.event, actor=env.owner, data={**data, "expected_version": 2}, action="test.replay")


@pytest.mark.parametrize("stage_env", ["hackathon"], indirect=True)
def test_late_failure_preserves_existing_application_draft(stage_env):
    from django.utils import timezone
    from apps.events.hackathons.admission_models import HackathonApplication
    env = stage_env
    draft = HackathonApplication.objects.create(event=env.event, member=env.owner, answers_snapshot='{"draft":"original"}')
    row = definition(env)
    prepared = prepare_inline(event=env.event, actor=env.owner, outer_operation_id=uuid4(), stage_forms=[payload(row)])
    with pytest.raises(RuntimeError), outer(env) as (event, locks):
        registration = EventRegistration.objects.create(event=event, member=env.owner, name="Maker",
            email="draft@example.test", phone="", registration_audience="accounts")
        draft.registration, draft.state, draft.submitted_at = registration, "submitted", timezone.now()
        draft.save()
        bind_locked(event=event, actor=env.owner, registration=registration, application=draft,
            prepared_stages=prepared, locks=locks)
        raise RuntimeError("injected outer receipt failure")
    draft.refresh_from_db()
    assert draft.state == "draft" and draft.registration_id is None
    assert draft.answers_snapshot == '{"draft":"original"}'
    assert not StageFormAssignment.objects.exists()
    assert not EventRegistration.objects.filter(event=env.event).exists()

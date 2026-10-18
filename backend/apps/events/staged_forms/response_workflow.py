"""Preparation is outside locks; answer/history/intent writes share one commit."""
from dataclasses import dataclass, field
from functools import partial
import json
from copy import deepcopy
from zoneinfo import ZoneInfo
from django.utils import timezone
from apps.accounts.saved_details.intents import ValidatedSaveInput, prepare_saved_detail_intent, insert_prepared_locked
from apps.events.contracts.subjects import StageResponseSubject
from apps.forms_schema.submission import validate_submission
from apps.payments.event_payouts.errors import require
from .definition_models import EventStageForm
from .response_models import StageFormAssignment, StageFormResponse, StageFormResponseRevision
from .policy import require_stage_schema
from .transactions import command, require_outer
from .upload_policy import resolve_reference
from .command_values import form_intent_status


@dataclass(frozen=True)
class PreparedResponse:
    subject: StageResponseSubject
    validated: object = field(repr=False)
    saved: object = field(repr=False)
    event_date_revision: int
    save_input: object = field(repr=False)
    operation_id: object
    outer_operation_id: object = None
    slot: str | None = None


def schema_context(response):
    event = response.event
    return {**require_stage_schema(response.form_revision.schema), "event_context": {
        "event_id": event.pk, "event_date_revision": event.event_date_revision,
        "timezone_name": event.timezone_name, "as_of_date": event.starts_at.astimezone(ZoneInfo(event.timezone_name)).date().isoformat()}}


def prepare(*, response, actor, data, operation_id, outer_operation_id=None, slot=None, subject=None, draft=False):
    require(response.owner_member_id == actor.pk, "not_found", status=404)
    subject = subject or StageResponseSubject(event_id=response.event_id, owner_member_id=actor.pk, subject_id=response.pk)
    schema = schema_context(response)
    require_stage_schema(schema, derivations=data.get("derivations", {}))
    if draft:
        schema = deepcopy(schema)
        for question in schema["questions"]:
            question["required"] = False
    validated = validate_submission(schema=schema, payload=data, subject=subject, context="stage",
        file_resolver=partial(resolve_reference, assignment=response.assignment))
    require(data["event_date_revision"] == response.event.event_date_revision, "event_date_changed")
    descriptor = {key: schema[key] for key in ("schema_version", "form_id", "revision")}
    form = ValidatedSaveInput(subject=subject, mapped_values=validated.profile_values,
        canonical_answers=validated.snapshot, form_descriptor=descriptor,
        event_date_revision=response.event.event_date_revision)
    saved = None if draft else prepare_saved_detail_intent(actor_id=actor.pk, subject=subject, validated_form=form,
        choices=validated.save_choices, base_versions=validated.saved_detail_versions, operation_id=operation_id,
        outer_operation_id=outer_operation_id, form_slot=slot)
    return PreparedResponse(subject, validated, saved, response.event.event_date_revision,
                            form, operation_id, outer_operation_id, slot)


def submit_locked(*, event, actor, response, assignment, prepared, data, locks, submit=True):
    from .prefill_provider import pending_binding
    require_outer(locks, event)
    require(response.event_id == assignment.event_id == event.pk and
        response.owner_member_id == assignment.owner_member_id == actor.pk and response.assignment_id == assignment.pk,
        "invalid_subject", status=404)
    require(response.version == data["expected_version"] and assignment.version == data["expected_assignment_version"], "stale_version")
    require(not submit or assignment.registration_id is not None and (
        assignment.application_id is None or assignment.application.state != "draft"), "canonical_participation_required")
    require(response.state in ("draft", "submitted") and assignment.state not in ("cancelled", "overdue")
        and not assignment.imported_paused and assignment.opens_at <= timezone.now() < assignment.effective_due_at
        and assignment.next_stage_locked_at is None, "stage_response_closed")
    require(prepared.event_date_revision == event.event_date_revision, "event_date_changed")
    bound = StageResponseSubject(event_id=event.pk, owner_member_id=actor.pk, subject_id=response.pk)
    require(prepared.subject.event_id == event.pk and prepared.subject.owner_member_id == actor.pk, "invalid_subject")
    require(prepared.subject.subject_id == response.pk if prepared.subject.subject_id else
        prepared.subject.creation_operation_id == assignment.creation_operation_id == prepared.operation_id, "invalid_subject")
    validated = prepared.validated
    require_stage_schema(validated.schema, derivations=validated.derivations)
    require((validated.schema["form_id"], validated.schema["revision"]) ==
        (response.form_revision.schema["form_id"], response.form_revision.revision)
        and assignment.pinned_form_revision_id == response.form_revision_id, "form_revision_changed")
    for answer in validated.snapshot["answers"]:
        if answer["type"] == "file":
            question = next(q for q in validated.schema["questions"] if q["id"] == answer["id"])
            for ref in answer["value"]:
                require(resolve_reference(assignment=assignment, question=question, reference=ref, locked=True), "stage_file_unavailable")
    response.answers_snapshot, response.answer_event_date_revision = json.dumps(validated.snapshot), event.event_date_revision
    if submit:
        sequence = (response.submitted_revisions.order_by("-revision").values_list("revision", flat=True).first() or 0) + 1
        revision = StageFormResponseRevision.objects.create(response=response, revision=sequence,
            form_revision=response.form_revision, answers_snapshot=response.answers_snapshot,
            submitted_at=timezone.now(), submitted_by=actor, date_revision=event.event_date_revision)
        response.state, response.submitted_at, response.current_submitted_revision = "submitted", revision.submitted_at, revision
        assignment.state, assignment.completed_response = "completed", response
        from .upload_workflow import attach_locked
        from .upload_models import StageFormAsset
        for answer in validated.snapshot["answers"]:
            if answer["type"] == "file":
                for ref in answer["value"]:
                    attach_locked(StageFormAsset.objects.select_for_update().get(pk=ref["asset_id"]), response=response)
    response.version, assignment.version = response.version + 1, assignment.version + 1
    response.save()
    assignment.save()
    intent_id = None
    if submit and prepared.saved:
        with pending_binding(response=response, validated=validated, operation_id=prepared.saved.operation_id,
            outer_operation_id=prepared.saved.outer_operation_id, slot=prepared.saved.form_slot):
            intent_id = insert_prepared_locked(prepared.saved, subject=bound, locks=locks)
    from apps.audit.services import record
    record(actor, "event.stage_form.submitted" if submit else "event.stage_form.draft_saved",
        makerspace=event.makerspace, target=response, meta={"assignment_id": assignment.pk,
            "revision_id": response.current_submitted_revision_id, "new_state": response.state})
    return {"response_id": response.pk, "assignment_id": assignment.pk, "version": response.version,
        "assignment_version": assignment.version, "state": response.state,
        "save_intent": str(intent_id) if intent_id else None,
        "save_operation_id": str(prepared.operation_id) if intent_id else None,
        "form_save_intents": [form_intent_status(
            slot=prepared.slot or f"stage:{assignment.stage_form_id}", operation_id=prepared.operation_id, intent_id=intent_id)]}


def save(*, event_id, actor, response_id, data, prepared, submit=True):
    with command(event_id=event_id, actor=actor, data=data,
        action=f"stage_response.{'submit' if submit else 'draft'}:{response_id}", owner=True, virtual=True) as ctx:
        if ctx.replay:
            return ctx.replay
        seed = StageFormResponse.objects.get(pk=response_id, event=ctx.event, owner_member=actor)
        from .lifecycle import reconcile_participant_locked
        from .trigger_service import resolve_participant
        reconcile_participant_locked(subject=resolve_participant(event=ctx.event, owner_id=actor.pk), locks=ctx.locks)
        EventStageForm.objects.select_for_update().get(pk=seed.assignment.stage_form_id)
        assignment = StageFormAssignment.objects.select_for_update().get(pk=seed.assignment_id)
        response = StageFormResponse.objects.select_for_update().get(pk=response_id)
        result = submit_locked(event=ctx.event, actor=ctx.actor, response=response, assignment=assignment,
            prepared=prepared, data=data, locks=ctx.locks, submit=submit)
        return ctx.finish(response, **{key: value for key, value in result.items() if key not in ("version", "state")})


def lock_at_deadline_locked(response, *, now):
    if response.state in ("draft", "submitted"):
        response.state = "locked"
        response.locked_at = response.answer_locked_at = now
        response.version += 1
        response.save()
        from apps.audit.services import record
        record(None, "event.stage_form.response_locked", makerspace=response.event.makerspace,
               target=response, meta={"response_id": response.pk, "new_state": "locked"})

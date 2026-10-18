"""Stage ownership and Saved-details binding never enter the DOB resolver."""
from contextlib import contextmanager
from contextvars import ContextVar
import json
from zoneinfo import ZoneInfo
from django.utils import timezone
from apps.accounts.models import User
from apps.accounts.saved_details.intents import digest
from apps.accounts.saved_details.prefill import PrefillContext
from apps.accounts.saved_details.subject_binding import VerifiedIntentBinding, VerifiedFormOperation
from apps.events.contracts.form_operations import child_form_operation_id
from apps.events.contracts.subjects import StageResponseSubject
from apps.events.models import Event
from apps.events.programme_locks import assert_lock_context
from apps.makerspaces.guards import require_module
from apps.payments.event_payouts.errors import require
from apps.presence.guard import require_active_account
from apps.tenant_migration.gate_runtime import assert_write_allowed
from .definition_models import EventStageForm
from .policy import require_stage_schema
from .response_models import StageFormResponse

_pending = ContextVar("stage_pending_bindings", default={})


def resolve_owner(subject):
    require(isinstance(subject, StageResponseSubject), "invalid_subject", status=404)
    if subject.subject_id:
        response = StageFormResponse.objects.select_related("assignment", "form_revision", "event__makerspace").get(
            pk=subject.subject_id, event_id=subject.event_id, owner_member_id=subject.owner_member_id)
        return response
    return None


@contextmanager
def pending_binding(*, response, validated, operation_id, outer_operation_id=None, slot=None):
    proof = None
    if outer_operation_id is not None:
        require(slot == f"stage:{response.assignment.stage_form_id}" and operation_id == child_form_operation_id(
            outer_operation_id, event_id=response.event_id, owner_id=response.owner_member_id, slot=slot), "invalid_subject")
        require(response.assignment.creation_operation_id == operation_id, "invalid_subject")
        proof = VerifiedFormOperation(outer_operation_id=outer_operation_id, slot=slot, operation_id=operation_id,
            event_id=response.event_id, owner_member_id=response.owner_member_id, subject_kind="stage_response", subject_id=response.pk)
    value = VerifiedIntentBinding(form_sha256=digest({key: validated.schema[key] for key in
        ("schema_version", "form_id", "revision")}), canonical_answer_sha256=digest(validated.snapshot),
        event_date_revision=response.answer_event_date_revision,
        chosen_fields=tuple(sorted(key for key, selected in validated.save_choices.items() if selected)), form_operation=proof)
    token = _pending.set({**_pending.get(), (response.pk, operation_id): value})
    try:
        yield
    finally:
        _pending.reset(token)


def require_binding(*, prepared_subject, actual_subject, operation_id, locks):
    assert_lock_context(locks)
    row = resolve_owner(actual_subject)
    require(row is not None and row.owner_member_id in locks.account_ids and row.event_id == locks.event_id,
            "invalid_subject", status=404)
    require(prepared_subject.event_id == row.event_id and prepared_subject.owner_member_id == row.owner_member_id,
            "invalid_subject", status=404)
    if prepared_subject.subject_id is None:
        require(prepared_subject.creation_operation_id == row.assignment.creation_operation_id == operation_id,
                "invalid_subject")
    else:
        require(prepared_subject.subject_id == row.pk, "invalid_subject")
    result = _pending.get().get((row.pk, operation_id))
    require(result is not None, "invalid_subject")
    return result


def resolve_context(*, actor_id, selector):
    event = Event.objects.select_related("makerspace").get(pk=selector["event_id"])
    actor = User.objects.get(pk=actor_id)
    require_active_account(actor, event.makerspace)
    require_module(event.makerspace, "events")
    assert_write_allowed(event.makerspace_id)
    subject = StageResponseSubject(event_id=event.pk, owner_member_id=actor.pk,
        subject_id=selector.get("subject_id"), creation_operation_id=selector.get("creation_operation_id"))
    response = resolve_owner(subject)
    if response:
        definition, revision = response.assignment.stage_form, response.form_revision
        locked = response.state in ("locked", "withdrawn") or response.assignment.effective_due_at <= timezone.now()
    else:
        from .trigger_service import resolve_participant, applicable
        definition = EventStageForm.objects.get(pk=selector["stage_form_id"], event=event, state="published")
        participant = resolve_participant(event=event, owner_id=actor.pk, creation_operation_id=subject.creation_operation_id)
        require(applicable(definition, participant) is not None, "stage_not_applicable", status=404)
        revision, locked = definition.current_revision, False
    schema = require_stage_schema(revision.schema)
    return PrefillContext(owner_id=actor.pk, event_id=event.pk, subject_kind="stage_response",
        subject=subject, stage_form_id=definition.pk, form_id=schema["form_id"], form_revision=revision.revision,
        event_date_revision=event.event_date_revision, as_of_date=event.starts_at.astimezone(ZoneInfo(event.timezone_name)).date(),
        questions=tuple(schema["questions"]), locked=locked)

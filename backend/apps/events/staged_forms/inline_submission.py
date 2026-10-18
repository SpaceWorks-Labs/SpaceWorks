"""R's half of G's outer submit bridge; never opens a second transaction.

G checks its outer replay first, prepares base/R forms, calls validate_conflicts,
then invokes bind_locked after its canonical registration/application writes.
Any failure propagates through G's outer atomic block, including intent/notice
or final receipt failure. No HTTP input is accepted as pending binding proof.
"""
from dataclasses import dataclass, field
from types import SimpleNamespace
from django.db import connection
from django.utils import timezone
from apps.accounts.saved_details.intents import validate_form_save_conflicts
from apps.events.contracts.form_operations import child_form_operation_id
from apps.events.contracts.subjects import StageResponseSubject
from apps.payments.event_payouts.errors import require
from .definition_models import EventStageForm
from .response_models import StageFormAssignment, StageFormResponse
from .response_workflow import prepare, submit_locked
from .stage_workflow import activate_locked
from .transactions import require_outer, lock_stage_parents
from .trigger_service import Participant, applicable


@dataclass(frozen=True)
class PreparedStage:
    definition_id: int
    definition_version: int
    form_revision_id: int
    prepared: object = field(repr=False)
    assignment_version: int | None = None
    response_version: int | None = None


def prepare_inline(*, event, actor, outer_operation_id, stage_forms):
    require(not connection.in_atomic_block, "prepare_outside_transaction")
    from apps.accounts.account_kind_guards import require_member_account
    from apps.presence.guard import require_active_account
    from apps.makerspaces.guards import require_module
    from apps.tenant_migration.gate_runtime import assert_write_allowed
    require_member_account(actor)
    require_active_account(actor, event.makerspace)
    require_module(event.makerspace, "events")
    assert_write_allowed(event.makerspace_id)
    require(isinstance(stage_forms, list) and len(stage_forms) <= 50, "invalid_stage_forms", status=400)
    ids = [item.get("stage_form_id") for item in stage_forms if isinstance(item, dict)]
    require(len(ids) == len(stage_forms) and all(type(pk) is int and pk > 0 for pk in ids)
        and len(set(ids)) == len(ids), "invalid_stage_forms", status=400)
    result = []
    for item in sorted(stage_forms, key=lambda value: value["stage_form_id"]):
        require(not set(item) - {"stage_form_id", "form", "answers", "derivations", "save_choices",
                                 "saved_detail_versions", "event_date_revision"}, "invalid_stage_forms", status=400)
        definition = EventStageForm.objects.get(pk=item["stage_form_id"], event=event, state="published")
        require(definition.stage == "application", "stage_not_inline", status=400)
        slot = f"stage:{definition.pk}"
        child = child_form_operation_id(outer_operation_id, event_id=event.pk, owner_id=actor.pk, slot=slot)
        subject = StageResponseSubject(event_id=event.pk, owner_member_id=actor.pk, creation_operation_id=child)
        candidate = applicable(definition, Participant(event, actor.pk, creation_operation_id=child))
        require(candidate is not None, "stage_not_applicable")
        assignment = StageFormAssignment.objects.filter(stage_form=definition, owner_member=actor).first()
        if assignment:
            require(assignment.creation_operation_id == child and assignment.registration_id is None
                and (assignment.application_id is None or assignment.application.state == "draft"), "stage_assignment_exists")
        response = SimpleNamespace(pk=None, owner_member_id=actor.pk, event_id=event.pk, event=event,
            form_revision=definition.current_revision, assignment=assignment)
        prepared = prepare(response=response, actor=actor, data=item, operation_id=child,
                           outer_operation_id=outer_operation_id, slot=slot, subject=subject)
        result.append(PreparedStage(definition.pk, definition.version, definition.current_revision_id, prepared,
            assignment.version if assignment else None, assignment.response.version if assignment else None))
    return tuple(result)


def validate_conflicts(prepared_stages, *, base_forms=None):
    forms = dict(base_forms or {})
    for item in prepared_stages:
        value = item.prepared
        forms[value.slot] = (value.save_input, value.validated.save_choices, value.validated.saved_detail_versions)
    validate_form_save_conflicts(forms)


def bind_locked(*, event, actor, registration, application, prepared_stages, locks):
    require_outer(locks, event)
    require(registration.event_id == event.pk and registration.member_id == actor.pk, "invalid_subject")
    require(application is None or (application.event_id == event.pk and application.member_id == actor.pk
        and application.registration_id == registration.pk), "invalid_subject")
    lock_stage_parents(event=event, owner_ids=(actor.pk,))
    definitions = {row.pk: row for row in EventStageForm.objects.select_for_update().filter(
        event=event, pk__in=[item.definition_id for item in prepared_stages]).order_by("pk")}
    operations, statuses = {}, []
    for item in prepared_stages:
        definition, prepared = definitions[item.definition_id], item.prepared
        require(definition.version == item.definition_version and definition.current_revision_id == item.form_revision_id,
                "form_revision_changed")
        subject = Participant(event, actor.pk, registration, application, prepared.operation_id)
        assignment = activate_locked(definition=definition, subject=subject, locks=locks)
        require(assignment is not None and assignment.creation_operation_id == prepared.operation_id, "invalid_subject")
        assignment = StageFormAssignment.objects.select_for_update().get(pk=assignment.pk)
        require(item.assignment_version is None and assignment.version == 1 or item.assignment_version == assignment.version,
                "stale_assignment_version")
        require(assignment.registration_id in (None, registration.pk) and assignment.application_id in (
            None, application.pk if application else None), "invalid_subject")
        assignment.registration, assignment.application = registration, application
        assignment.save(update_fields=["registration", "application"])
        response = StageFormResponse.objects.select_for_update().get(assignment=assignment)
        require(item.response_version is None and response.version == 1 or item.response_version == response.version,
                "stale_response_version")
        result = submit_locked(event=event, actor=actor, response=response, assignment=assignment, prepared=prepared,
            data={"expected_version": response.version, "expected_assignment_version": assignment.version}, locks=locks)
        operations[prepared.slot] = {"operation_id": str(prepared.operation_id), "kind": "stage_response", "subject_id": response.pk}
        statuses.extend(result["form_save_intents"])
    # Required applicable forms omitted by the caller cannot leave a partial signup.
    participant = Participant(event, actor.pk, registration, application)
    for row in EventStageForm.objects.filter(event=event, state="published", stage="application", required=True):
        if applicable(row, participant):
            require(row.pk in definitions, "stage_incomplete", stage_form_ids=[row.pk])
    return {"form_operations": operations, "form_save_intents": statuses}

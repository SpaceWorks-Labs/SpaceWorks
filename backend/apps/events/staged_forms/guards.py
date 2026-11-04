"""Readiness never treats an absent assignment as a completed form."""
from django.db import connection
from django.utils import timezone
from apps.payments.event_payouts.errors import PayoutError, require
from .definition_models import EventStageForm
from .response_models import StageFormAssignment
from .trigger_service import applicable


def readiness(subject, action, *, now=None):
    require(action in ("rsvp", "check_in", "claim_submit"), "invalid_stage_action", status=400)
    now = now or timezone.now()
    definitions = {row.pk: row for row in EventStageForm.objects.filter(event=subject.event, state="published")
                   if row.required and action in row.blocked_actions}
    rows = list(StageFormAssignment.objects.filter(event=subject.event, owner_member_id=subject.owner_member_id)
        .select_related("stage_form", "completed_response__current_submitted_revision"))
    by_definition = {row.stage_form_id: row for row in rows}
    from .lifecycle import frozen_policy
    # Retired pinned assignments remain binding. Existing assignments keep their
    # audience/trigger decision, even if roles or definition settings change.
    for row in rows:
        policy = frozen_policy(row)
        if policy.required and action in policy.blocked_actions:
            definitions.setdefault(row.stage_form_id, row.stage_form)
    missing, warnings, versions = [], [], []
    for pk, definition in definitions.items():
        row = by_definition.get(pk)
        if row is None:
            if applicable(definition, subject, now=now):
                (missing if definition.missed_action == "block" else warnings if definition.missed_action == "warn" else []).append(pk)
            continue
        policy = frozen_policy(row)
        if not policy.required or action not in policy.blocked_actions:
            continue
        versions.append([row.pk, row.version, row.due_revision])
        if row.imported_paused or row.state == "cancelled" or row.opens_at > now:
            continue
        response = row.completed_response
        submitted = response.current_submitted_revision if response and response.current_submitted_revision_id else None
        if not (row.state == "completed" and response and response.assignment_id == row.pk
                and response.state in ("submitted", "locked") and submitted
                and submitted.form_revision_id == row.pinned_form_revision_id):
            (missing if policy.missed_action == "block" else warnings if policy.missed_action == "warn" else []).append(pk)
    return {"ready": not missing, "action": action, "stage_form_ids": sorted(missing),
            "warning_stage_form_ids": sorted(warnings), "assignment_versions": sorted(versions)}


def require_complete_locked(subject, action):
    require(connection.in_atomic_block, "locked_transaction_required")
    result = readiness(subject, action)
    if not result["ready"]:
        raise PayoutError("stage_incomplete", action=action, stage_form_ids=result["stage_form_ids"])
    if result["warning_stage_form_ids"]:
        from .notices import enqueue_warning_locked
        enqueue_warning_locked(subject, result["warning_stage_form_ids"], action)
    return result

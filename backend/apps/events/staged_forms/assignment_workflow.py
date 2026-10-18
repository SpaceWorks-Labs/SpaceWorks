"""Manager CAS commands retain responses/history and never change admission."""
from django.utils import timezone
from apps.events import event_authority
from apps.events.programme.form_models import EventFormRevision
from apps.payments.event_payouts.errors import require
from .response_models import StageFormAssignment, StageFormResponse
from .transactions import command
from .policy import require_stage_schema


def manage(*, event_id, actor, assignment_id, data, action):
    require(action in ("cancel", "reassign", "extend", "reopen"), "invalid_stage_action", status=400)
    seed = StageFormAssignment.objects.get(pk=assignment_id, event_id=event_id)
    with command(event_id=event_id, actor=actor, data=data, action=f"stage_assignment.{action}:{assignment_id}",
        permission="manage_registrations", account_ids=(seed.owner_member_id,)) as ctx:
        if ctx.replay:
            return ctx.replay
        from .definition_models import EventStageForm
        definition = EventStageForm.objects.select_for_update().get(pk=seed.stage_form_id, event=ctx.event)
        row = StageFormAssignment.objects.select_for_update().get(pk=assignment_id, stage_form=definition)
        response = StageFormResponse.objects.select_for_update().filter(assignment=row).first()
        ctx.cas(row)
        require(data["expected_stage_form_version"] == definition.version, "stale_stage_form_version")
        require(data["expected_response_version"] == (response.version if response else None), "stale_response_version")
        if response is None and action != "cancel":
            response = StageFormResponse(assignment=row, event=ctx.event, owner_member_id=row.owner_member_id,
                form_revision=row.pinned_form_revision, answer_event_date_revision=ctx.event.event_date_revision)
        from .lifecycle import frozen_policy
        policy = frozen_policy(row)
        if policy.required and policy.missed_action == "block":
            require(event_authority.can_manage_grants(ctx.actor, ctx.event), "full_manager_required", status=403)
        require(data.get("confirmed") is True, "confirmation_required", status=400)
        now, old = timezone.now(), row.state
        if action == "cancel":
            require(row.state != "cancelled", "stage_assignment_cancelled")
            row.state, row.cancelled_by, row.cancelled_at = "cancelled", ctx.actor, now
            row.cancellation_reason_code, row.cancellation_reason = data["reason_code"], data["reason"]
            row.completed_response = None
            if response:
                response.state = "locked" if response.current_submitted_revision_id else "withdrawn"
                response.locked_at = response.answer_locked_at = now
        else:
            require(data["due_at"] > (now if action == "reassign" else max(now, row.opens_at)), "invalid_stage_deadline", status=400)
            if action == "reassign":
                revision = EventFormRevision.objects.get(pk=data["replacement_form_revision_id"],
                    event=ctx.event, form_key="stage", selector_kind="stage", selector_id=definition.pk)
                from apps.audit.models import AuditLog
                published = AuditLog.objects.filter(makerspace_id=ctx.event.makerspace_id,
                    action="event.stage_form.published", target_type="events.eventstageform", target_id=str(definition.pk),
                    meta__stage_form_id=definition.pk, meta__revision_id=revision.pk).exists()
                require(published, "replacement_revision_not_published")
                require_stage_schema(revision.schema)
                row.pinned_form_revision = response.form_revision = revision
                row.completed_response = None
                row.reassigned_by, row.reassigned_at = ctx.actor, now
                row.reassignment_reason_code, row.reassignment_reason = data["reason_code"], data["reason"]
                response.answers_snapshot = "{}"
                response.state, response.submitted_at = "draft", None
                row.cancelled_by, row.cancelled_at = None, None
                row.cancellation_reason_code, row.cancellation_reason = "", ""
                row.imported_paused = False
            else:
                require(row.state != "cancelled", "stage_assignment_cancelled")
                require(action == "reopen" or data["due_at"] > row.effective_due_at, "extension_must_move_forward")
                response.state = "submitted" if row.completed_response_id else "draft"
            row.state = "open" if action == "reassign" else "completed" if row.completed_response_id else "open"
            if action == "reassign":
                row.opens_at = now
            row.effective_due_at, row.extension_reason = data["due_at"], data["reason"]
            row.extended_by, row.extended_at = ctx.actor, now
            row.due_revision += 1
            row.next_stage_locked_at = None
            from .lifecycle import reached_rank
            from .trigger_service import resolve_participant
            row.policy_snapshot = {**row.policy_snapshot, "lock_suppressed_through_rank": reached_rank(
                resolve_participant(event=ctx.event, owner_id=row.owner_member_id), now)}
            response.locked_at = response.answer_locked_at = None
        row.version += 1
        row.save()
        if response:
            response.version += bool(response.pk)
            response.save()
        ctx.audit("event.stage_form." + action, row, assignment_id=row.pk, old_state=old, new_state=row.state,
            response_id=response.pk if response else None, reason_code=data["reason_code"])
        from .notices import enqueue_locked
        enqueue_locked(row, {"cancel": "cancelled", "reassign": "reassigned", "extend": "extended", "reopen": "reopened"}[action])
        return ctx.finish(row, response_id=response.pk if response else None, response_version=response.version if response else None,
                          pinned_form_revision_id=row.pinned_form_revision_id,
                          due_at=row.effective_due_at.isoformat(), allowed_actions=["reassign"] if action == "cancel"
                          else ["cancel", "reassign", "extend", "reopen"])


def reactivate_imported_locked(row, *, due_at, actor):
    """Only the confirmed catch-up job calls this after live authoring checks."""
    if not row.imported_paused or row.state == "cancelled":
        return row
    require(due_at > timezone.now(), "invalid_stage_deadline")
    from .response_models import StageFormResponse
    response = StageFormResponse.objects.select_for_update().get(assignment=row)
    row.imported_paused, row.opens_at, row.effective_due_at = False, timezone.now(), due_at
    row.state = "completed" if row.completed_response_id else "open"
    row.next_stage_locked_at = None
    from .lifecycle import reached_rank
    from .trigger_service import resolve_participant
    row.policy_snapshot = {**row.policy_snapshot, "lock_suppressed_through_rank": reached_rank(
        resolve_participant(event=row.event, owner_id=row.owner_member_id), timezone.now())}
    row.version, row.due_revision = row.version + 1, row.due_revision + 1
    response.state = "submitted" if row.completed_response_id else "draft"
    response.locked_at = response.answer_locked_at = None
    response.version += 1
    row.save()
    response.save()
    from apps.audit.services import record
    record(actor, "event.stage_form.import_reactivated", makerspace=row.event.makerspace, target=row,
           meta={"assignment_id": row.pk, "due_revision": row.due_revision})
    from .notices import enqueue_locked
    enqueue_locked(row, "reopened")
    return row

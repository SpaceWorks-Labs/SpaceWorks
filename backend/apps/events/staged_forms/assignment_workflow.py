"""Manager CAS commands retain responses/history and never change admission."""
from django.utils import timezone
from apps.events import event_authority
from apps.events.programme.form_models import EventFormRevision
from apps.payments.event_payouts.errors import require
from .response_models import StageFormAssignment
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
        response = row.response.__class__.objects.select_for_update().get(assignment=row)
        ctx.cas(row)
        require(data["expected_stage_form_version"] == definition.version, "stale_stage_form_version")
        require(data["expected_response_version"] == response.version, "stale_response_version")
        if definition.required and definition.missed_action == "block":
            require(event_authority.can_manage_grants(ctx.actor, ctx.event), "full_manager_required", status=403)
        require(data.get("confirmed") is True, "confirmation_required", status=400)
        now, old = timezone.now(), row.state
        if action == "cancel":
            require(row.state != "cancelled", "stage_assignment_cancelled")
            row.state, row.cancelled_by, row.cancelled_at = "cancelled", ctx.actor, now
            row.cancellation_reason_code, row.cancellation_reason = data["reason_code"], data["reason"]
            response.state = "locked" if response.current_submitted_revision_id else "withdrawn"
            response.locked_at = now
        else:
            require(data["due_at"] > max(now, row.opens_at), "invalid_stage_deadline", status=400)
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
                response.current_submitted_revision, response.answers_snapshot = None, "{}"
                response.state, response.submitted_at = "draft", None
            else:
                require(row.state != "cancelled", "stage_assignment_cancelled")
                require(action == "reopen" or data["due_at"] > row.effective_due_at, "extension_must_move_forward")
                response.state = "submitted" if response.current_submitted_revision_id else "draft"
            row.state = "completed" if response.current_submitted_revision_id else "open"
            row.effective_due_at, row.extension_reason = data["due_at"], data["reason"]
            row.extended_by, row.extended_at = ctx.actor, now
            row.due_revision += 1
            row.next_stage_locked_at = None
            response.locked_at = response.answer_locked_at = None
        row.version, response.version = row.version + 1, response.version + 1
        response.save()
        row.save()
        ctx.audit("event.stage_form." + action, row, assignment_id=row.pk, old_state=old, new_state=row.state,
            response_id=response.pk, reason_code=data["reason_code"])
        from .notices import enqueue_locked
        enqueue_locked(row, {"cancel": "cancelled", "reassign": "reassigned", "extend": "extended", "reopen": "reopened"}[action])
        return ctx.finish(row, response_id=response.pk, response_version=response.version,
                          pinned_form_revision_id=row.pinned_form_revision_id,
                          due_at=row.effective_due_at.isoformat())

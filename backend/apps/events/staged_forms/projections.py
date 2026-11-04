"""Revision reads use independent organizer and finance disclosure projections."""
import json
from django.utils import timezone
from apps.accounts import rbac
from apps.events import event_authority
from apps.forms_schema.sensitive_policy import project_schema, project_answers
from apps.payments.event_payouts.errors import require


def assignment_summary(row):
    from .lifecycle import frozen_policy
    policy = frozen_policy(row)
    from django.core.exceptions import ObjectDoesNotExist
    try:
        response = row.response
    except ObjectDoesNotExist:
        response = None
    state = row.state
    if state in ("scheduled", "open") and timezone.now() >= row.effective_due_at:
        state = "overdue"
    return {"id": row.pk, "stage_form_id": row.stage_form_id, "title": row.stage_form.title,
        "version": row.version, "state": state, "due_at": row.effective_due_at,
        "opens_at": row.opens_at, "due_revision": row.due_revision,
        "pinned_form_revision_id": row.pinned_form_revision_id,
        "response_id": response.pk if response else None, "response_version": response.version if response else None,
        "required": policy.required, "blocked_actions": policy.blocked_actions,
        "schema": {key: row.pinned_form_revision.schema[key] for key in ("schema_version", "form_id", "revision")}}


def detail(*, actor, response, revision=None, finance=False, owner=False):
    event = response.event
    if owner:
        require(actor.pk == response.owner_member_id, "not_found", status=404)
    elif finance:
        require(rbac.can(actor, rbac.Action.VIEW_FINANCE, event.makerspace_id), "finance_required", status=403)
    else:
        event_authority.require(actor, event, "manage_registrations")
        require(rbac.can(actor, rbac.Action.VIEW_AUDIT, event.makerspace_id), "audit_required", status=403)
    selected = response.submitted_revisions.get(revision=revision) if revision else (
        None if owner and (response.state == "draft" or response.current_submitted_revision_id and
            response.current_submitted_revision.form_revision_id != response.form_revision_id) else response.current_submitted_revision)
    if not owner:
        require(selected is not None, "submitted_response_required", status=404)
    snapshot = json.loads(selected.answers_snapshot if selected else response.answers_snapshot)
    schema = selected.form_revision.schema if selected else response.form_revision.schema
    live = response.assignment.stage_form.current_revision.schema
    viewer = "owner" if owner else "finance" if finance else "organizer"
    from apps.forms_schema.sensitive_policy import permitted_questions
    allowed = {q["id"] for q in permitted_questions(schema, viewer=viewer, current_schema=live)}
    def file_projector(*, question, references):
        from .upload_reads import project_references
        return project_references(response=response, selected=selected, question=question,
                                  references=references, owner=owner, finance=finance)
    projected_schema = project_schema(schema, viewer=viewer, current_schema=schema if owner else live)
    answers = project_answers(schema, snapshot, viewer=viewer, current_schema=schema if owner else live, file_projector=file_projector)
    review = {"date_revision": selected.date_revision if selected else response.answer_event_date_revision,
        "locked": response.locked_at is not None or response.assignment.next_stage_locked_at is not None
                  or timezone.now() >= response.assignment.effective_due_at}
    omitted = sorted(allowed - {row["id"] for row in snapshot.get("answers", [])})
    if not owner:
        return {"event_id": event.pk, "stage_form_id": response.assignment.stage_form_id,
            "assignment_id": response.assignment_id, "response_id": response.pk, "response_version": response.version,
            "response_revision": selected.revision, "form": projected_schema, "submitted_at": selected.submitted_at,
            "projection": viewer, "answers": answers, "answer_review": review, "omitted_question_ids": omitted}
    from .trigger_service import participation_live
    assignment = response.assignment
    editable = (response.state in ("draft", "submitted") and assignment.state not in ("cancelled", "overdue")
        and not assignment.imported_paused and assignment.next_stage_locked_at is None
        and assignment.opens_at <= timezone.now() < assignment.effective_due_at
        and event.status != "cancelled" and participation_live(assignment))
    actions = ["save", "upload"] if editable else []
    if editable and assignment.registration_id and (not assignment.application_id or assignment.application.state != "draft"):
        actions.append("submit")
    return {"id": response.pk, "version": response.version, "state": response.state,
        "assignment": assignment_summary(response.assignment), "selected_revision": selected.revision if selected else None,
        "schema": projected_schema, "answers": answers, "answer_review": review, "omitted_question_ids": omitted,
        "allowed_actions": actions,
        "event_date_revision": response.event.event_date_revision}

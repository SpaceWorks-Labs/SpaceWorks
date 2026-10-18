"""Revision reads use independent organizer and finance disclosure projections."""
import json
from django.utils import timezone
from apps.accounts import rbac
from apps.events import event_authority
from apps.forms_schema.sensitive_policy import project_schema, project_answers
from apps.payments.event_payouts.errors import require


def assignment_summary(row):
    state = row.state
    if state in ("scheduled", "open") and timezone.now() >= row.effective_due_at:
        state = "overdue"
    return {"id": row.pk, "stage_form_id": row.stage_form_id, "title": row.stage_form.title,
        "version": row.version, "state": state, "due_at": row.effective_due_at,
        "opens_at": row.opens_at, "due_revision": row.due_revision,
        "pinned_form_revision_id": row.pinned_form_revision_id,
        "response_id": row.response.pk, "response_version": row.response.version,
        "required": row.stage_form.required, "blocked_actions": row.stage_form.blocked_actions}


def detail(*, actor, response, revision=None, finance=False, owner=False):
    event = response.event
    if owner:
        require(actor.pk == response.owner_member_id, "not_found", status=404)
    elif finance:
        require(rbac.can(actor, rbac.Action.VIEW_FINANCE, event.makerspace_id), "finance_required", status=403)
    else:
        event_authority.require(actor, event, "manage_registrations")
        require(rbac.can(actor, rbac.Action.VIEW_AUDIT, event.makerspace_id), "audit_required", status=403)
    selected = response.submitted_revisions.get(revision=revision) if revision else response.current_submitted_revision
    if not owner:
        require(selected is not None, "submitted_response_required", status=404)
    snapshot = json.loads(selected.answers_snapshot if selected else response.answers_snapshot)
    schema = selected.form_revision.schema if selected else response.form_revision.schema
    live = response.assignment.stage_form.current_revision.schema
    viewer = "owner" if owner else "finance" if finance else "organizer"
    return {"id": response.pk, "version": response.version, "state": response.state,
        "assignment": assignment_summary(response.assignment), "selected_revision": selected.revision if selected else None,
        "schema": project_schema(schema, viewer=viewer, current_schema=live),
        "answers": project_answers(schema, snapshot, viewer=viewer, current_schema=live),
        "event_date_revision": response.event.event_date_revision}

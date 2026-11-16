from uuid import uuid4
import pytest
from django.http import Http404
from apps.audit.models import AuditLog
from apps.events.contributions import role_workflow
from apps.events.contributions.errors import ProgrammeError
from tests.events.programme.contributions.completion_helpers import role_setup, command
from tests.events.programme.contributions.test_role_forms import payload


@pytest.mark.django_db(transaction=True)
def test_auto_approval_locks_issuer_and_subject_and_runs_policy(settings):
    _, event, posting, _, users, roles, adapter, manager = role_setup(settings)
    posting.approval_required = False
    posting.save(update_fields=["approval_required"])
    row = roles[0]
    row.state = "draft"
    row.save(update_fields=["state"])
    seen = []
    def approval(**kwargs):
        assert {manager.pk, users[0].pk} <= set(kwargs["locks"].account_ids)
        seen.append("policy")
    adapter.forms.require_approval_locked = approval
    result = role_workflow.edit(actor=users[0], event_id=event.pk, assignment_id=row.pk,
        payload={**payload(), "expected_version": row.version}, submit=True)
    assert result.row.state == "approved" and result.row.approved_by_id == manager.pk
    assert seen == ["policy"] and result.row.answer_locked_at is not None


@pytest.mark.django_db(transaction=True)
def test_revoked_issuer_or_missing_coc_rolls_back_auto_submit(settings):
    _, event, posting, _, users, roles, adapter, manager = role_setup(settings)
    posting.approval_required = False
    posting.save(update_fields=["approval_required"])
    row = roles[0]
    row.state = "draft"
    row.save(update_fields=["state"])
    def refuse(**kwargs):
        raise ProgrammeError("coc_required", "Accept the code of conduct.", status=400)
    adapter.forms.require_approval_locked = refuse
    with pytest.raises(ProgrammeError):
        role_workflow.edit(actor=users[0], event_id=event.pk, assignment_id=row.pk,
            payload={**payload(), "expected_version": row.version}, submit=True)
    row.refresh_from_db()
    assert row.state == "draft" and row.submitted_at is None
    adapter.forms.require_approval_locked = lambda **kwargs: None
    manager.is_active = False
    manager.save(update_fields=["is_active"])
    with pytest.raises(ProgrammeError):
        role_workflow.edit(actor=users[0], event_id=event.pk, assignment_id=row.pk,
            payload={**payload(), "expected_version": row.version}, submit=True)
    row.refresh_from_db()
    assert row.state == "draft"


@pytest.mark.django_db
def test_explicit_decline_completion_and_foreign_owner_refusal(settings):
    _, event, _, _, users, roles, _, manager = role_setup(settings)
    row = roles[0]
    result = role_workflow.transition(actor=manager, event_id=event.pk, assignment_id=row.pk,
        payload=command(row, reason="Duty finished"), action="complete")
    assert result.row.state == "completed"
    assert AuditLog.objects.filter(action="event.programme.role.complete").exists()
    row = roles[1]
    row.state = "proposed"
    row.save(update_fields=["state"])
    with pytest.raises(Http404):
        role_workflow.transition(actor=users[0], event_id=event.pk, assignment_id=row.pk,
            payload=command(row), action="decline")
    result = role_workflow.transition(actor=users[1], event_id=event.pk, assignment_id=row.pk,
        payload=command(row), action="decline")
    assert result.row.state == "declined"


@pytest.mark.django_db
def test_imported_role_cannot_approve_without_fresh_owner_revision(settings):
    _, event, _, _, _, roles, _, manager = role_setup(settings)
    row = roles[0]
    row.state, row.imported_inert = "applied", True
    row.save(update_fields=["state", "imported_inert"])
    with pytest.raises(ProgrammeError, match="Reconfirm"):
        role_workflow.transition(actor=manager, event_id=event.pk, assignment_id=row.pk,
            payload=command(row), action="approve")
    result = role_workflow.transition(actor=manager, event_id=event.pk, assignment_id=row.pk,
        payload=command(row, reason="Confirm at this venue"), action="reconfirm")
    assert result.row.state == "draft" and result.row.consent_revision is None

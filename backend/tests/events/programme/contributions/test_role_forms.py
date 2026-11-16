from types import SimpleNamespace
from uuid import uuid4
from django.db import connection
import pytest
from apps.events.contributions import role_workflow
from apps.events.contributions.errors import ProgrammeError
from apps.events.contributions.models import EventRoleAssignment
from apps.events.models import EventRegistration
from tests.events.programme.contributions.helpers import setup_shift
from tests.events.ticketing_helpers import account


def payload():
    return {"operation_id": uuid4(), "expected_version": 0, "form": {"schema_version": 2,
        "form_id": "volunteer", "revision": 1}, "answers": {}, "derivations": {},
        "save_choices": {}, "saved_detail_versions": {}, "event_date_revision": 1}


@pytest.mark.django_db(transaction=True)
def test_role_only_draft_prepares_outside_transaction_and_binds_owner_fence(settings):
    _, event, posting, _, _, _, adapter = setup_shift(settings)
    user = account(f"role-only-{uuid4().hex[:8]}")
    adapter.users.append(user)
    phases = []
    def prepare(**kwargs):
        assert not connection.in_atomic_block
        assert kwargs["subject"].owner_member_id == user.pk
        assert kwargs["submit"] is False
        phases.append("prepare")
        return object()
    def apply_locked(**kwargs):
        assert connection.in_atomic_block
        assert user.pk in kwargs["locks"].account_ids
        assert kwargs["subject"].subject_id is not None
        phases.append("apply")
        return {"answers_json": '{"version":2,"answers":[]}', "schema_version": 2}
    adapter.forms = SimpleNamespace(prepare=prepare, apply_locked=apply_locked)
    result = role_workflow.apply(actor=user, event_id=event.pk, posting_id=posting.pk, payload=payload())
    assert result.row.state == "draft" and phases == ["prepare", "apply"]
    assert not EventRegistration.objects.filter(member=user).exists()


@pytest.mark.django_db(transaction=True)
def test_preparation_failure_and_locked_intent_refusal_leave_no_application(settings):
    _, event, posting, _, _, _, adapter = setup_shift(settings)
    user = account(f"failed-prepare-{uuid4().hex[:8]}")
    adapter.users.append(user)
    def refuse(**kwargs):
        raise ProgrammeError("pii_write_fenced", "Protected writes are closed.", status=423)
    adapter.forms = SimpleNamespace(prepare=refuse)
    with pytest.raises(ProgrammeError):
        role_workflow.apply(actor=user, event_id=event.pk, posting_id=posting.pk, payload=payload())
    assert not EventRoleAssignment.objects.filter(event=event, member=user).exists()
    adapter.forms = SimpleNamespace(prepare=lambda **kwargs: object(), apply_locked=refuse)
    with pytest.raises(ProgrammeError):
        role_workflow.apply(actor=user, event_id=event.pk, posting_id=posting.pk, payload=payload())
    assert not EventRoleAssignment.objects.filter(event=event, member=user).exists()


@pytest.mark.django_db(transaction=True)
def test_auto_approval_issuer_change_during_preparation_refuses_without_partial_submit(settings):
    from tests.events.programme.contributions.completion_helpers import role_setup
    from tests.events.collab_helpers import make_staff
    space, event, posting, _, users, roles, adapter, manager = role_setup(settings)
    replacement = make_staff(space, username="replacement")
    posting.approval_required = False
    posting.save(update_fields=["approval_required"])
    roles[0].state = "draft"
    roles[0].save(update_fields=["state"])
    def prepare(**kwargs):
        posting.permission_issuer = replacement
        posting.save(update_fields=["permission_issuer"])
        return object()
    adapter.forms.prepare = prepare
    with pytest.raises(ProgrammeError) as error:
        role_workflow.edit(actor=users[0], event_id=event.pk, assignment_id=roles[0].pk,
            payload={**payload(), "expected_version": roles[0].version}, submit=True)
    assert error.value.detail["code"] == "issuer_changed"
    roles[0].refresh_from_db()
    assert roles[0].state == "draft" and roles[0].submitted_at is None

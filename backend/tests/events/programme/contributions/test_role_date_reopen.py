import pytest
from django.utils import timezone
from rest_framework.exceptions import APIException
from apps.events.contributions import role_workflow
from apps.events.contributions.models import EventRoleAnswerRevision
from apps.events.mentoring.import_export import export_role_owner
from tests.events.programme.contributions.completion_helpers import role_setup, command


@pytest.mark.django_db(transaction=True)
def test_reopen_archives_markers_and_calls_p_under_subject_fences(settings):
    _, event, _, _, users, roles, adapter, manager = role_setup(settings)
    row = roles[0]
    row.answer_locked_at = timezone.now()
    row.answers = '{"version":2,"answers":[{"id":"age","type":"age_at_event","derivation_id":123}]}'
    row.save(update_fields=["answer_locked_at", "answers"])
    frozen = []
    def reopen(**kwargs):
        assert users[0].pk in kwargs["locks"].account_ids
        assert kwargs["subject"].subject_id == row.pk
        frozen.append(kwargs["previous_version"])
    adapter.forms.reopen_locked = reopen
    result = role_workflow.transition(actor=manager, event_id=event.pk, assignment_id=row.pk,
        payload=command(row, reason="Event date moved"), action="reopen_answers")
    revision = EventRoleAnswerRevision.objects.get(assignment=row)
    assert revision.answers == row.answers and revision.locked_at == row.answer_locked_at
    assert result.row.state == "draft" and result.row.answer_locked_at is None
    assert result.row.date_review_required and result.row.consent_revision is None
    assert frozen == [row.version]
    assert "date_of_birth" not in revision.answers and '"age":20' not in revision.answers


@pytest.mark.django_db
def test_missing_p_reopen_hook_rolls_back_archive_and_state(settings):
    _, event, _, _, _, roles, adapter, manager = role_setup(settings)
    del adapter.forms.reopen_locked
    from apps.events.contributions.errors import ProgrammeError
    with pytest.raises(ProgrammeError) as error:
        role_workflow.transition(actor=manager, event_id=event.pk, assignment_id=roles[0].pk,
            payload=command(roles[0], reason="Moved date"), action="reopen_answers")
    assert error.value.status_code == 503
    assert not EventRoleAnswerRevision.objects.exists()
    roles[0].refresh_from_db()
    assert roles[0].state == "approved"


@pytest.mark.django_db
def test_dob_source_export_is_owner_only_even_for_manager(settings):
    _, _, _, _, users, roles, _, manager = role_setup(settings)
    assert export_role_owner(actor=users[0], row=roles[0])["subject_id"] == roles[0].pk
    for actor in (users[1], manager):
        with pytest.raises(APIException) as error:
            export_role_owner(actor=actor, row=roles[0])
        assert getattr(error.value, "status_code", None) in (403, 404)

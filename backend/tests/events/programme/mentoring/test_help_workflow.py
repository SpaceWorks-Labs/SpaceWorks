from uuid import uuid4
import pytest
from apps.events.mentoring import help_workflow
from apps.events.mentoring.models import EventHelpComment, EventHelpRequest, MentorNotificationIntent
from apps.events.contributions.errors import ProgrammeError
from tests.events.programme.mentoring.helpers import setup_help, help_payload


@pytest.mark.django_db
def test_mentor_origin_does_not_claim_and_team_cancel_releases_claim(settings):
    _, event, users, mentors, roles, team, _ = setup_help(settings)
    row = help_workflow.create(actor=mentors[0], event_id=event.pk, payload=help_payload(team.pk), mentor_origin=True).row
    assert row.origin == "mentor" and row.state == "open" and row.claimed_by_id is None
    claimed = help_workflow.command(actor=mentors[0], event_id=event.pk, help_id=row.pk,
        payload={"operation_id": uuid4(), "expected_version": row.version}, action="claim").row
    assert claimed.claimed_by_id == roles[0].pk and claimed.first_claimed_at is not None
    cancelled = help_workflow.command(actor=users[0], event_id=event.pk, help_id=row.pk,
        payload={"operation_id": uuid4(), "expected_version": claimed.version}, action="cancel", member_surface=True).row
    assert cancelled.state == "cancelled" and cancelled.claimed_by_id is None
    assert not any("Private wiring" in str(row.__dict__) for row in MentorNotificationIntent.objects.all())


@pytest.mark.django_db
def test_unrelated_mentor_cannot_resolve_another_claim(settings):
    _, event, users, mentors, _, team, _ = setup_help(settings)
    row = help_workflow.create(actor=users[0], event_id=event.pk, payload=help_payload(team.pk)).row
    row = help_workflow.command(actor=mentors[0], event_id=event.pk, help_id=row.pk,
        payload={"operation_id": uuid4(), "expected_version": row.version}, action="claim").row
    with pytest.raises(ProgrammeError) as error:
        help_workflow.command(actor=mentors[1], event_id=event.pk, help_id=row.pk,
            payload={"operation_id": uuid4(), "expected_version": row.version, "resolution_note": "not mine"}, action="resolve")
    assert error.value.status_code == 404
    row.refresh_from_db()
    assert row.state == "claimed"


@pytest.mark.django_db
def test_comment_replay_adds_one_comment_and_does_not_change_claim(settings):
    _, event, users, _, _, team, _ = setup_help(settings)
    row = help_workflow.create(actor=users[0], event_id=event.pk, payload=help_payload(team.pk)).row
    payload = {"operation_id": uuid4(), "expected_version": row.version, "body": "We have a multimeter."}
    first = help_workflow.comment(actor=users[0], event_id=event.pk, help_id=row.pk, payload=payload, member_surface=True)
    replay = help_workflow.comment(actor=users[0], event_id=event.pk, help_id=row.pk, payload=payload, member_surface=True)
    assert first.row.pk == replay.row.pk and replay.replayed
    assert EventHelpComment.objects.filter(request=row).count() == 1
    row.refresh_from_db()
    assert row.state == "open" and row.claimed_by_id is None


@pytest.mark.django_db
def test_foreign_team_and_off_shift_are_refused_without_new_rows(settings):
    _, event, users, mentors, roles, team, _ = setup_help(settings)
    roles[0].availability = []
    roles[0].save(update_fields=["availability"])
    with pytest.raises(ProgrammeError) as error:
        help_workflow.create(actor=mentors[0], event_id=event.pk, payload=help_payload(team.pk), mentor_origin=True)
    assert error.value.detail["code"] == "mentor_off_shift"
    from rest_framework.exceptions import NotFound
    with pytest.raises(NotFound):
        help_workflow.create(actor=users[1], event_id=event.pk, payload=help_payload(team.pk))
    assert not EventHelpRequest.objects.exists()

from uuid import uuid4
import pytest
from apps.events.mentoring import assignment_workflow
from apps.events.mentoring.models import MentorTeamAssignment, MentorAssignmentRun
from tests.events.collab_helpers import make_staff
from tests.events.programme.mentoring.helpers import setup_help


@pytest.mark.django_db(transaction=True)
def test_bulk_run_persists_all_coverage_and_replays_no_duplicate(settings):
    space, event, _, _, _, team, _ = setup_help(settings)
    manager = make_staff(space)
    payload = {"operation_id": uuid4(), "expected_version": getattr(event, "version", 1),
               "team_ids": [team.pk], "mode": "round_robin"}
    result = assignment_workflow.assign(actor=manager, event_id=event.pk, payload=payload, proposed=True)
    replay = assignment_workflow.assign(actor=manager, event_id=event.pk, payload=payload, proposed=True)
    assert result.row.pk == replay.row.pk and replay.replayed
    assert MentorAssignmentRun.objects.count() == 1
    assert len(result.row.decisions) == 1 and result.row.unsatisfied_team_ids == []
    mapping = MentorTeamAssignment.objects.get(run_id=payload["operation_id"])
    assert mapping.state == "proposed"
    for action, state in (("activate", "active"), ("end", "ended")):
        mapping = assignment_workflow.transition(actor=manager, event_id=event.pk, assignment_id=mapping.pk,
            payload={"operation_id": uuid4(), "expected_version": mapping.version}, action=action).row
        assert mapping.state == state
    assert mapping.ended_at is not None


@pytest.mark.django_db
def test_unsatisfied_run_is_durable_even_with_zero_eligible_mentors(settings):
    space, event, _, _, roles, team, _ = setup_help(settings)
    from apps.events.mentoring.models import MentorProfile
    MentorProfile.objects.filter(assignment__in=roles).update(availability=[])
    for role in roles:
        role.availability = []
        role.save(update_fields=["availability"])
    result = assignment_workflow.assign(actor=make_staff(space), event_id=event.pk,
        payload={"operation_id": uuid4(), "expected_version": getattr(event, "version", 1), "team_ids": [team.pk], "mode": "round_robin"})
    assert result.row.decisions == [] and result.row.unsatisfied_team_ids == [team.pk]
    assert not MentorTeamAssignment.objects.exists()

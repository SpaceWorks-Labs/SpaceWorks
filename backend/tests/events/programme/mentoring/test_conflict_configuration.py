from uuid import uuid4
import pytest
from rest_framework.exceptions import APIException
from apps.events.mentoring import configuration_workflow, policy
from apps.events.mentoring.serializers_configuration import HelpTypeWriteSerializer
from apps.events.contributions.errors import ProgrammeError
from tests.events.programme.mentoring.helpers import setup_help


@pytest.mark.django_db
def test_mentor_can_declare_own_conflict_but_not_another_mentors(settings):
    _, event, _, mentors, roles, team, _ = setup_help(settings)
    payload = {"operation_id": uuid4(), "expected_version": 0, "mentor_assignment_id": roles[0].pk,
        "team_id": team.pk, "kind": "declared", "active": True, "reason": "Project collaborator"}
    result = configuration_workflow.conflict(actor=mentors[0], event_id=event.pk, payload=payload)
    assert result.row.active
    assert policy.is_conflicted(member_id=mentors[0].pk, team_id=team.pk)
    with pytest.raises(APIException) as error:
        configuration_workflow.conflict(actor=mentors[1], event_id=event.pk,
            payload={**payload, "operation_id": uuid4(), "expected_version": result.row.version})
    assert getattr(error.value, "status_code", None) == 403


@pytest.mark.parametrize("field,value", [("open_limit", 0), ("claim_minutes", 61), ("expiry_minutes", 14), ("age_limit", 18)])
def test_help_policy_bounds_are_validated_at_boundary(field, value):
    serializer = HelpTypeWriteSerializer(data={"operation_id": str(uuid4()), "expected_version": 0,
        "key": "pcb", "label": "PCB help", field: value})
    assert not serializer.is_valid() and field in serializer.errors


@pytest.mark.django_db
def test_removing_profile_availability_cannot_revive_role_schedule_fallback(settings):
    _, event, _, mentors, roles, _, _ = setup_help(settings)
    from apps.events.mentoring.models import MentorProfile
    row = MentorProfile.objects.get(assignment=roles[0])
    configuration_workflow.save_profile(actor=mentors[0], event_id=event.pk, assignment_id=roles[0].pk,
        payload={"operation_id": uuid4(), "expected_version": row.version, "availability": []})
    with pytest.raises(ProgrammeError) as error:
        policy.mentor_for(mentors[0], event)
    assert error.value.detail["code"] == "mentor_off_shift"

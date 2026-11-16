from datetime import timedelta
from uuid import uuid4
from django.apps import apps
from django.db import transaction
from django.utils import timezone
from apps.events.contributions.models import EventRoleAssignment, EventGrantEntitlement
from apps.events.mentoring.models import MentorProfile, EventHelpType
from apps.events.models import EventStaffGrant
from tests.events.programme.contributions.helpers import setup_shift
from tests.events.ticketing_helpers import account


def setup_help(settings):
    space, event, _, _, users, _, adapter = setup_shift(settings)
    mentors, roles = [], []
    for _ in range(2):
        user = account(f"mentor-{uuid4().hex[:10]}")
        role = EventRoleAssignment.objects.create(event=event, makerspace=space, member=user,
            role="mentor", state="approved", approved_by=adapter.issuer, availability=[{"starts_at": event.starts_at.isoformat(),
                                                           "ends_at": event.ends_at.isoformat()}])
        MentorProfile.objects.create(event=event, makerspace=space, assignment=role, skills=["pcb"])
        grant = EventStaffGrant.objects.create(event=event, makerspace=space, user=user,
            granted_by=adapter.issuer, permissions=["mentor_queue"])
        EventGrantEntitlement.objects.create(event=event, makerspace=space, grant=grant,
            source_kind="role", role_assignment=role, permissions=["mentor_queue"], created_by=adapter.issuer)
        mentors.append(user); roles.append(role)
    team = led_team(event, users[0], f"Team-{uuid4().hex[:6]}")
    adapter.members[team.pk] = [users[0].pk]
    EventHelpType.objects.create(event=event, makerspace=space, key="pcb", label="PCB help", skill_tags=["pcb"])
    return space, event, users, mentors, roles, team, adapter


def led_team(event, leader, name):
    """An active team must hold its leader as an active member (deferred DB guard)."""
    with transaction.atomic():
        application = apps.get_model("events", "HackathonApplication").objects.create(event=event, member=leader)
        team = apps.get_model("events", "HackathonTeam").objects.create(event=event, leader=leader, name=name,
            normalized_name=name.casefold())
        apps.get_model("events", "HackathonTeamMember").objects.create(event=event, team=team, member=leader,
            application=application, creator=leader, state="active")
    return team


def help_payload(team_id):
    return {"operation_id": uuid4(), "expected_version": 0, "team_id": team_id,
            "type_key": "pcb", "summary": "Private wiring question", "zone": {"table": "B4"}}

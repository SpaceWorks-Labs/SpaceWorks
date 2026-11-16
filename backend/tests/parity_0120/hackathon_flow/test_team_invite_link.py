"""Decision 296 review: a team invitation link keeps working after the team changes (a comment, an edit)."""
import pytest
from apps.events.hackathons.team_models import HackathonTeam
from apps.events.hackathons.team_invitations import accept, invite
from apps.events.hackathons.team_workflow import create
from tests.events.programme.admission.test_support import cmd, submitted, world  # noqa: F401 (fixture)

pytestmark = pytest.mark.django_db


def confirmed(world, member=None):
    app = submitted(world, member)
    app.state = "confirmed"
    app.save()
    return app


def test_an_invitation_minted_before_a_team_change_still_admits_the_invitee(world):
    confirmed(world)
    confirmed(world, world.other)
    team = create(event_id=world.event.pk, actor=world.owner, data=cmd(0, name="Builders"))
    _, token = invite(event_id=world.event.pk, team_id=team.pk, actor=world.owner, data=cmd(team.version, rotate=True))
    minted_at = HackathonTeam.objects.get(pk=team.pk).version
    HackathonTeam.objects.filter(pk=team.pk).update(version=minted_at + 3)  # comments / edits since the link was shared
    joined = accept(event_id=world.event.pk, team_id=team.pk, actor=world.other, data=cmd(minted_at, token=token))
    assert joined.memberships.filter(member=world.other, state="active").exists()


def test_a_leader_decision_on_a_join_request_still_checks_the_version(world):
    from apps.events.hackathons.admission_errors import ProgrammeError
    from apps.events.hackathons.team_models import HackathonTeamMember
    confirmed(world)
    second = confirmed(world, world.other)
    team = create(event_id=world.event.pk, actor=world.owner, data=cmd(0, name="Builders"))
    request = HackathonTeamMember.objects.create(event=world.event, team=team, application=second, member=world.other,
                                                 creator=world.other, state="requested")
    with pytest.raises(ProgrammeError) as caught:
        accept(event_id=world.event.pk, team_id=team.pk, actor=world.owner, data=cmd(team.version + 9, request_id=request.pk))
    assert caught.value.detail["code"] == "stale_version"

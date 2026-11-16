"""Decision 301 review (FIX-HACK): a leader declines a join request, against the real database.

Reuses the programme admission `world` (hackathon config, confirmed applications, authority doubles).
Organisers cannot decline a join request: their moderation routes are rename, move member, delete and
restore only, so there is no organiser-side decline to test.
"""
import pytest

from apps.audit.models import AuditLog
from apps.events.hackathons import team_invitations, team_notifications
from apps.events.hackathons.admission_errors import ProgrammeError
from apps.events.hackathons.team_models import HackathonTeam, HackathonTeamMember
from apps.events.hackathons.team_projection import project_team
from apps.events.hackathons.team_workflow import create
from tests.events.programme.admission.test_support import cmd, submitted, world  # noqa: F401

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.fixture
def requested(world, monkeypatch):
    """A forming team led by `owner`, seeking members, with a pending request from `other`."""
    world.config.finder_enabled = True
    world.config.save()
    submitted(world, state="confirmed")
    submitted(world, world.other, state="confirmed")
    team = create(event_id=world.event.pk, actor=world.owner, data=cmd(0, name="Makers"))
    HackathonTeam.objects.filter(pk=team.pk).update(seeking_members=True)
    team.refresh_from_db()
    sent = []
    monkeypatch.setattr(team_notifications, "emit", lambda **kw: sent.append(kw))
    team = team_invitations.join_request(event_id=world.event.pk, team_id=team.pk, actor=world.other,
                                         data=cmd(team.version))
    request = HackathonTeamMember.objects.get(team=team, member=world.other)
    sent.clear()
    return world, team, request, sent


def test_the_leader_declines_the_requester_is_declined_audited_and_told(requested):
    world, team, request, sent = requested
    declined = team_invitations.decline(event_id=world.event.pk, team_id=team.pk, actor=world.owner,
                                        data=cmd(team.version, request_id=request.pk))
    request.refresh_from_db()
    assert request.state == "declined" and request.left_at is not None
    assert declined.version == team.version + 1
    assert AuditLog.objects.filter(action="event.hackathon.team_join_declined").count() == 1
    assert [(call["event"], call["recipient"].pk) for call in sent] == [("team_join_declined", world.other.pk)]
    assert call_text(sent[0]) == "The team leader declined your request to join their event team."
    # the request is gone from the leader's list and the requester may ask again
    assert project_team(team, actor=world.owner, config=world.config)["join_requests"] == []
    team.refresh_from_db()
    again = team_invitations.join_request(event_id=world.event.pk, team_id=team.pk, actor=world.other,
                                          data=cmd(team.version))
    assert again.memberships.filter(member=world.other, state="requested").count() == 1


def call_text(call):
    return call["rendered"]()["text"]


def test_a_non_leader_cannot_decline(requested):
    world, team, request, sent = requested
    with pytest.raises(ProgrammeError) as refused:
        team_invitations.decline(event_id=world.event.pk, team_id=team.pk, actor=world.other,
                                 data=cmd(team.version, request_id=request.pk))
    assert refused.value.status_code == 403 and refused.value.detail["code"] == "leader_required"
    request.refresh_from_db()
    assert request.state == "requested" and sent == []


def test_a_decided_or_unknown_request_is_a_404_and_a_stale_version_is_refused(requested):
    from django.http import Http404
    world, team, request, _sent = requested
    with pytest.raises(ProgrammeError) as stale:
        team_invitations.decline(event_id=world.event.pk, team_id=team.pk, actor=world.owner,
                                 data=cmd(team.version + 5, request_id=request.pk))
    assert stale.value.detail["code"] == "stale_version"
    with pytest.raises(Http404):
        team_invitations.decline(event_id=world.event.pk, team_id=team.pk, actor=world.owner,
                                 data=cmd(team.version, request_id=request.pk + 999))
    team_invitations.decline(event_id=world.event.pk, team_id=team.pk, actor=world.owner,
                             data=cmd(team.version, request_id=request.pk))
    team.refresh_from_db()
    with pytest.raises(Http404):  # already declined
        team_invitations.decline(event_id=world.event.pk, team_id=team.pk, actor=world.owner,
                                 data=cmd(team.version, request_id=request.pk))


def test_a_declined_notice_survives_later_team_changes(requested, monkeypatch):
    from types import SimpleNamespace
    world, team, request, _sent = requested
    # The admission world doubles the feature gates; this test is about the version, not the module switches.
    monkeypatch.setattr(team_notifications, "programme_live", lambda event: True)
    team_invitations.decline(event_id=world.event.pk, team_id=team.pk, actor=world.owner,
                             data=cmd(team.version, request_id=request.pk))
    HackathonTeam.objects.filter(pk=team.pk).update(version=team.version + 10)  # comments, other joins...
    envelope = SimpleNamespace(event="team_join_declined", recipient_id=world.other.pk, source_id=str(team.pk),
                               makerspace_id=world.space.pk, revision="2", context={"event_id": world.event.pk,
                                                                                    "request_id": request.pk})
    assert team_notifications.team_eligible(envelope) is True

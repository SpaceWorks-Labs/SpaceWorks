"""E-F4: the two read additions the team screens need.

* the member team projection offers `handover` / `remove_member` / `cancel_registration` only while
  `events.team_moderation` is on, and only to the people who may run them;
* the organiser team detail lists the active roster (member id, leader flag, team-profile name) so
  "move member" can name who moves. Names never fall back to private account data.
"""
import pytest
from django.utils import timezone

from apps.events.hackathons.team_models import HackathonTeamMember
from apps.events.hackathons.team_projection import project_team
from apps.events.hackathons.team_workflow import create
from apps.events.hackathons.views_admin_teams import project_detail
from tests.events.programme.admission.test_support import cmd, submitted, world  # noqa: F401

pytestmark = pytest.mark.django_db(transaction=True)


def two_person_team(world):
    apps = [submitted(world, member, state="confirmed") for member in (world.owner, world.other)]
    team = create(event_id=world.event.pk, actor=world.owner, data=cmd(0, name="Makers"))
    HackathonTeamMember.objects.create(event=world.event, team=team, application=apps[1], member=world.other,
                                       creator=world.other, state="active", joined_at=timezone.now())
    team.refresh_from_db()
    return team


def switch(world, on):
    features = [key for key in world.space.enabled_features if key != "events.team_moderation"]
    world.space.enabled_features = [*features, "events.hackathons", *(["events.team_moderation"] if on else [])]
    world.space.save(update_fields=["enabled_features"])


def test_moderation_actions_follow_the_switch_and_the_leader(world):  # noqa: F811
    switch(world, True)
    team = two_person_team(world)
    leader = project_team(team, actor=world.owner, config=world.config)["allowed_actions"]
    member = project_team(team, actor=world.other, config=world.config)["allowed_actions"]
    assert {"handover", "remove_member", "cancel_registration"} <= set(leader)
    assert "cancel_registration" in member
    assert "handover" not in member and "remove_member" not in member


def test_moderation_actions_disappear_when_the_switch_is_off(world):  # noqa: F811
    switch(world, False)
    team = two_person_team(world)
    actions = project_team(team, actor=world.owner, config=world.config)["allowed_actions"]
    assert not {"handover", "remove_member", "cancel_registration"} & set(actions)


def test_locked_team_keeps_handover_but_not_removal(world):  # noqa: F811
    switch(world, True)
    team = two_person_team(world)
    team.state = "locked"
    team.save(update_fields=["state"])
    actions = project_team(team, actor=world.owner, config=world.config)["allowed_actions"]
    assert "handover" in actions
    assert "remove_member" not in actions and "cancel_registration" not in actions


def test_organiser_detail_lists_the_active_roster_without_private_names(world):  # noqa: F811
    switch(world, True)
    team = two_person_team(world)
    detail = project_detail(team)
    assert [row["member_id"] for row in detail["members"]] == [world.owner.pk, world.other.pk]
    assert [row["is_leader"] for row in detail["members"]] == [True, False]
    # The fixture's public-profile port returns nothing: no account name leaks in its place.
    assert {row["display_name"] for row in detail["members"]} == {""}
    assert detail["member_count"] == 2

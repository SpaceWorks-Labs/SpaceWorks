"""E-B3 team handover, removal, leave-and-cancel, organiser moderation with undo, and the max guard."""
from datetime import timedelta

import pytest
from django.utils import timezone

from apps.events.hackathons import team_lifecycle, team_moderation
from apps.events.hackathons.admission_config import largest_active_team, update as update_config
from apps.events.hackathons.admission_errors import ProgrammeError
from apps.events.hackathons.team_models import HackathonTeam, HackathonTeamMember
from apps.events.hackathons.team_workflow import create
from tests.events.programme.admission.test_support import cmd, submitted, world  # noqa: F401

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.fixture
def space_on(world):  # noqa: F811
    world.space.enabled_features = [*world.space.enabled_features, "events.hackathons", "events.team_moderation"]
    world.space.save(update_fields=["enabled_features"])
    world.config.team_max = 3
    world.config.save()
    return world


def team_of(world, *members, name="Makers"):
    apps = [submitted(world, member, state="confirmed") for member in members]
    team = create(event_id=world.event.pk, actor=members[0], data=cmd(0, name=name))
    for app, member in zip(apps[1:], members[1:]):
        HackathonTeamMember.objects.create(event=world.event, team=team, application=app, member=member,
                                           creator=member, state="active", joined_at=timezone.now())
    team.refresh_from_db()
    return team


def code(call):
    with pytest.raises(ProgrammeError) as raised:
        call()
    return str(raised.value.detail.get("code") if hasattr(raised.value, "detail") else raised.value)


def test_handover_to_a_non_member_is_refused_and_to_a_member_works(space_on):
    world = space_on
    team = team_of(world, world.owner, world.other)
    from tests.events.ticketing_helpers import account
    stranger = account("a-stranger")
    assert "invalid_leader" in code(lambda: team_lifecycle.transfer_leadership(
        event_id=world.event.pk, team_id=team.pk, actor=world.owner, data=cmd(team.version, new_leader_id=stranger.pk)))
    team_lifecycle.transfer_leadership(event_id=world.event.pk, team_id=team.pk, actor=world.owner,
                                       data=cmd(team.version, new_leader_id=world.other.pk))
    team.refresh_from_db()
    assert team.leader_id == world.other.pk


def test_only_the_leader_can_hand_over(space_on):
    world = space_on
    team = team_of(world, world.owner, world.other)
    assert "leader_required" in code(lambda: team_lifecycle.transfer_leadership(
        event_id=world.event.pk, team_id=team.pk, actor=world.other, data=cmd(team.version, new_leader_id=world.other.pk)))


def test_removing_the_leader_is_refused_and_removing_a_member_frees_them(space_on):
    world = space_on
    team = team_of(world, world.owner, world.other)
    assert "leader_cannot_be_removed" in code(lambda: team_lifecycle.remove_member(
        event_id=world.event.pk, team_id=team.pk, actor=world.owner, data=cmd(team.version, member_id=world.owner.pk)))
    team_lifecycle.remove_member(event_id=world.event.pk, team_id=team.pk, actor=world.owner,
                                 data=cmd(team.version, member_id=world.other.pk))
    assert HackathonTeamMember.objects.get(team=team, member=world.other).state == "removed"


def test_switch_off_hides_the_new_team_actions(world):  # noqa: F811
    team = team_of(world, world.owner, world.other)
    assert "not_found" in code(lambda: team_lifecycle.transfer_leadership(
        event_id=world.event.pk, team_id=team.pk, actor=world.owner, data=cmd(team.version, new_leader_id=world.other.pk)))


def test_leave_can_cancel_the_registration_and_notifies_the_new_leader(space_on):
    world = space_on
    team = team_of(world, world.owner, world.other)
    from apps.events.hackathons.admission_models import HackathonApplication
    team_lifecycle.leave(event_id=world.event.pk, team_id=team.pk, actor=world.owner,
                         data=cmd(team.version, cancel_registration=True))
    team.refresh_from_db()
    assert team.leader_id == world.other.pk
    assert HackathonApplication.objects.get(event=world.event, member=world.owner).state == "withdrawn"


def test_organiser_rename_and_name_clash(space_on):
    world = space_on
    first = team_of(world, world.owner, name="Alpha")
    from tests.events.ticketing_helpers import account
    second = team_of(world, account("a-third"), name="Beta")
    team_moderation.rename(event_id=world.event.pk, team_id=first.pk, actor=world.owner, data=cmd(first.version, name="Gamma"))
    first.refresh_from_db()
    assert first.name == "Gamma"
    assert "team_name_taken" in code(lambda: team_moderation.rename(
        event_id=world.event.pk, team_id=second.pk, actor=world.owner, data=cmd(second.version, name="gamma")))


def test_move_respects_the_maximum_and_moves_the_member(space_on):
    world = space_on
    from tests.events.ticketing_helpers import account
    source = team_of(world, world.owner, world.other, name="Source")
    target = team_of(world, account("a-t1"), name="Target")
    team_moderation.move_member(event_id=world.event.pk, team_id=source.pk, actor=world.owner,
                                data=cmd(source.version, member_id=world.other.pk, to_team_id=target.pk))
    assert HackathonTeamMember.objects.get(member=world.other, state="active").team_id == target.pk
    world.config.team_max = 2
    world.config.save()
    again = HackathonTeam.objects.get(pk=source.pk)
    assert "capacity_full" in code(lambda: team_moderation.move_member(
        event_id=world.event.pk, team_id=again.pk, actor=world.owner,
        data=cmd(again.version, member_id=world.owner.pk, to_team_id=target.pk)))


def test_delete_then_undo_inside_the_window_and_refused_after(space_on):
    world = space_on
    team = team_of(world, world.owner, world.other)
    team_moderation.delete(event_id=world.event.pk, team_id=team.pk, actor=world.owner, data=cmd(team.version))
    team.refresh_from_db()
    assert team.state == "disbanded" and team.deleted_at is not None
    assert not HackathonTeamMember.objects.filter(team=team, state="active").exists()
    team_moderation.restore(event_id=world.event.pk, team_id=team.pk, actor=world.owner, data=cmd(team.version))
    team.refresh_from_db()
    assert team.state == "forming" and team.memberships.filter(state="active").count() == 2

    team_moderation.delete(event_id=world.event.pk, team_id=team.pk, actor=world.owner, data=cmd(team.version))
    team.refresh_from_db()
    HackathonTeam.objects.filter(pk=team.pk).update(deleted_at=timezone.now() - timedelta(minutes=6))
    team.refresh_from_db()
    assert "undo_expired" in code(lambda: team_moderation.restore(
        event_id=world.event.pk, team_id=team.pk, actor=world.owner, data=cmd(team.version)))


def test_max_guard_refuses_a_maximum_below_the_largest_team(space_on):
    world = space_on
    team_of(world, world.owner, world.other)
    assert largest_active_team(world.event) == 2
    assert "team_max_below_largest_team" in code(lambda: update_config(
        event_id=world.event.pk, actor=world.owner,
        data=cmd(world.config.version, team_mode="team_together", team_min=1, team_max=1)))

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from django.db import close_old_connections, transaction
from django.utils import timezone
import pytest
from apps.events.hackathons.admission_cohorts import roster_hash
from apps.events.hackathons.admission_errors import ProgrammeError
from apps.events.hackathons.admission_models import HackathonApplicationCohort
from apps.events.hackathons.admission_rsvp import rsvp
from apps.events.hackathons.team_models import HackathonTeam, HackathonTeamMember
from apps.events.hackathons.team_workflow import create
from apps.events.hackathons.team_lifecycle import leave
from tests.events.programme.admission.test_support import world, submitted, cmd

pytestmark = pytest.mark.django_db(transaction=True)


def test_pending_requests_do_not_count_as_active_team_slots(world):
    first, second = submitted(world), submitted(world, world.other)
    first.state = second.state = "confirmed"
    first.save(); second.save()
    team = create(event_id=world.event.pk, actor=world.owner, data=cmd(0, name="Makers"))
    HackathonTeamMember.objects.create(event=world.event, team=team, application=second, member=world.other, creator=world.other, state="requested")
    assert team.memberships.filter(state="active").count() == 1


def test_longest_member_inherits_leadership_on_leave(world):
    first, second = submitted(world), submitted(world, world.other)
    first.state = second.state = "confirmed"
    first.save(); second.save()
    team = create(event_id=world.event.pk, actor=world.owner, data=cmd(0, name="Makers"))
    HackathonTeamMember.objects.create(event=world.event, team=team, application=second, member=world.other,
        creator=world.other, state="active", joined_at=timezone.now())
    leave(event_id=world.event.pk, team_id=team.pk, actor=world.owner, data=cmd(team.version))
    team.refresh_from_db()
    assert team.leader_id == world.other.pk and team.state == "forming"


def test_cohort_rsvp_only_confirms_when_everyone_accepts_and_all_seats_fit(world):
    world.config.team_mode = "team_together"
    world.config.save()
    world.event.capacity = 2
    world.event.save()
    first, second = submitted(world), submitted(world, world.other)
    with transaction.atomic():  # the team and its active leader commit together
        team = HackathonTeam.objects.create(event=world.event, leader=world.owner, name="Cohort", normalized_name="cohort")
        cohort = HackathonApplicationCohort.objects.create(event=world.event, team=team, state="offered", sealed_roster_hash="a" * 64)
        for app in (first, second):
            app.cohort = cohort
            app.save()
            HackathonTeamMember.objects.create(event=world.event, team=team, application=app, member=app.member,
                creator=app.member, state="active", joined_at=timezone.now())
    cohort.sealed_roster_hash = roster_hash(list(team.memberships.all()))
    cohort.save()
    rsvp(event_id=world.event.pk, actor=world.owner, data=cmd(first.version, decision="accept"))
    first.refresh_from_db()
    assert first.state == "offered" and first.registration.status == "pending_approval"
    rsvp(event_id=world.event.pk, actor=world.other, data=cmd(second.version, decision="accept"))
    first.refresh_from_db(); second.refresh_from_db(); cohort.refresh_from_db()
    assert first.state == second.state == cohort.state == "confirmed"


def test_one_cohort_decline_ends_every_offer(world):
    first, second = submitted(world), submitted(world, world.other)
    with transaction.atomic():  # the team and its active leader commit together
        team = HackathonTeam.objects.create(event=world.event, leader=world.owner, name="Group", normalized_name="group")
        cohort = HackathonApplicationCohort.objects.create(event=world.event, team=team, state="offered")
        for app in (first, second):
            app.cohort = cohort
            app.save()
            HackathonTeamMember.objects.create(event=world.event, team=team, application=app, member=app.member,
                creator=app.member, state="active", joined_at=timezone.now())
    rsvp(event_id=world.event.pk, actor=world.owner, data=cmd(first.version, decision="decline"))
    first.refresh_from_db(); second.refresh_from_db()
    assert first.state == second.state == "declined"
    assert [value for _, value in world.bridge.calls] == ["cancel", "cancel"]

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from uuid import uuid4
from django.apps import apps
from django.db import close_old_connections
from django.utils import timezone
import pytest
from apps.events.contributions.models import EventRolePosting, EventShift
from apps.events.contributions.errors import ProgrammeError
from apps.events.mentoring import office_hours_workflow, round_workflow
from apps.events.mentoring.models import OfficeHoursBooking, MentorRound, MentorRoundLock
from tests.events.programme.mentoring.helpers import led_team, setup_help


def concurrently(function):
    def call(index):
        close_old_connections()
        try:
            try:
                return function(index)
            except ProgrammeError as exc:
                return str(exc.detail["code"])
        finally:
            close_old_connections()
    with ThreadPoolExecutor(max_workers=2) as pool:
        return list(pool.map(call, [0, 1]))


@pytest.mark.django_db(transaction=True)
def test_office_hours_last_team_place_has_one_winner(settings):
    space, event, users, _, roles, team, adapter = setup_help(settings)
    other = led_team(event, users[1], "Other bench")
    adapter.members[other.pk] = [users[1].pk]
    posting = EventRolePosting.objects.create(event=event, makerspace=space, role="mentor", title="Mentor sessions",
        opens_at=event.starts_at, closes_at=event.ends_at, state="open")
    slot = EventShift.objects.create(event=event, makerspace=space, posting=posting, kind="office_hours",
        mentor_assignment=roles[0], task="PCB office hours", capacity=1,
        starts_at=timezone.now() + timedelta(minutes=30), ends_at=timezone.now() + timedelta(minutes=50),
        signup_deadline=timezone.now() + timedelta(minutes=20))
    teams = [team, other]
    result = concurrently(lambda index: office_hours_workflow.book(actor=users[index], event_id=event.pk,
        slot_id=slot.pk, payload={"operation_id": uuid4(), "expected_version": slot.version,
                                 "team_id": teams[index].pk}).row.state)
    assert sorted(result) == ["booked", "office_hours_full"]
    assert OfficeHoursBooking.objects.filter(slot=slot, state="booked").count() == 1


@pytest.mark.django_db(transaction=True)
def test_round_claim_race_then_old_generation_is_refused(settings):
    space, event, _, mentors, _, team, _ = setup_help(settings)
    round = MentorRound.objects.create(event=event, makerspace=space, index=1, key="idea", label="Idea",
        opens_at=event.starts_at, closes_at=event.ends_at, state="live")
    result = concurrently(lambda index: round_workflow.visit(actor=mentors[index], event_id=event.pk,
        round_id=round.pk, team_id=team.pk, payload={"operation_id": uuid4(), "expected_version": round.version},
        action="claim").row.generation)
    assert set(result) == {1, "team_busy"}
    assert MentorRoundLock.objects.filter(round=round, team=team).count() == 1
    old = MentorRoundLock.objects.get(round=round, team=team)
    previous_uuid, previous_generation = old.lease_uuid, old.generation
    old.expires_at = timezone.now() - timedelta(seconds=1)
    old.save(update_fields=["expires_at"])
    next_mentor = next(user for user in mentors if user.pk != old.mentor.member_id)
    new = round_workflow.visit(actor=next_mentor, event_id=event.pk, round_id=round.pk, team_id=team.pk,
        payload={"operation_id": uuid4(), "expected_version": round.version}, action="claim").row
    with pytest.raises(ProgrammeError) as error:
        round_workflow.visit(actor=next_mentor, event_id=event.pk, round_id=round.pk, team_id=team.pk,
            payload={"operation_id": uuid4(), "expected_version": new.version,
                     "lease_uuid": previous_uuid, "generation": previous_generation}, action="heartbeat")
    assert error.value.detail["code"] == "lease_lost"

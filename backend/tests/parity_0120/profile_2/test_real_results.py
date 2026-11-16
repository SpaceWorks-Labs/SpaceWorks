"""Verified achievements and project import against REAL judging/submission rows (decisions 302c/d, 303c).

Uses the hack-money `world` fixture (a real hackathon with judged, finalized and published results,
real submissions and sealed snapshots) instead of patched seams.
"""
import pytest
from django.utils import timezone

from apps.accounts.models import User
from apps.events.judging.models_results import EventAward, EventResultRound
from apps.events.judging.results_unpublish import unpublish
from apps.events.judging.results_workflow import finalize, publish
from apps.events.models import Event
from apps.events.submissions.models_projects import HackathonSubmission
from apps.makerspaces.models import AccountProject
from apps.makerspaces.profile_achievements import derived_achievements
from tests.events.pairwise_helpers import command
from tests.hackmoney_local.helpers import projects, world  # noqa: F401  (fixture re-export)
from tests.hackmoney_local.prize_helpers import winning_award

from .conftest import client_for

pytestmark = pytest.mark.django_db


def award_rows(user):
    return [row for row in derived_achievements(user) if row["kind"] == "award"]


def go_public(world):
    Event.objects.filter(pk=world.event.pk).update(
        is_public=True, listing="listed", page_state="live", status="published")


def test_published_award_shows_for_every_sealed_member_whatever_their_spaces(world):  # noqa: F811
    award, members = winning_award(world)
    go_public(world)
    for pk in members:
        rows = award_rows(User.objects.get(pk=pk))
        assert [(r["rank"], r["prize_name"], r["verified_by"]) for r in rows] == [
            (1, "Best build", world.space.name)]
    assert award_rows(User.objects.create_user(username="not-on-the-team")) == []


def test_award_from_a_private_or_unlisted_event_never_shows(world):  # noqa: F811
    _, members = winning_award(world)
    user = User.objects.get(pk=members[0])
    for values in ({"is_public": False}, {"listing": "unlisted"}, {"page_state": "offline"}, {"status": "draft"}):
        go_public(world)
        Event.objects.filter(pk=world.event.pk).update(**values)
        assert award_rows(user) == [], values


def test_corrected_result_replaces_the_old_row_and_never_duplicates(world):  # noqa: F811
    award, members = winning_award(world)
    go_public(world)
    user = User.objects.get(pk=members[0])
    round_ids = list(EventResultRound.objects.filter(result=award.result).values_list("round_id", flat=True))
    corrected = finalize(world.event.pk, actor=world.manager, correction=True, data=command(
        award.result.version, round_ids=round_ids, integrity_reviewed=True, reason="Scoring typo fixed",
        awards=[{"prize_id": award.prize_id, "snapshot_id": award.submission_snapshot_id, "rank": award.rank}]))
    # Before the correction is announced the PREVIOUS publication is still the public one.
    assert len(award_rows(user)) == 1
    publish(world.event.pk, actor=world.manager,
            data=command(corrected["version"], result_revision_id=corrected["id"]))
    assert EventAward.objects.filter(submission_snapshot_id=award.submission_snapshot_id).count() == 2
    assert len(award_rows(user)) == 1, "only the latest publication counts, never both revisions"


def test_withdrawn_result_disappears_and_republication_restores_it(world):  # noqa: F811
    award, members = winning_award(world)
    go_public(world)
    user = User.objects.get(pk=members[0])
    assert len(award_rows(user)) == 1
    unpublish(world.event.pk, actor=world.manager, data=command(award.result.version))
    assert award_rows(user) == []
    publish(world.event.pk, actor=world.manager,
            data=command(award.result.version, result_revision_id=award.result_id))
    assert len(award_rows(user)) == 1


def test_peoples_choice_winner_shows_only_while_the_event_is_public(world):  # noqa: F811
    from apps.events.judging.models_peoples_choice import PeoplesChoiceResult, PeoplesChoiceStanding

    snapshot_id = world.snapshots[0]
    leader = User.objects.get(pk=world.ports.snaps[snapshot_id].member_ids[0])
    result = PeoplesChoiceResult.objects.create(
        event=world.event, prize_name="Crowd favourite", total_votes=9, published_at=timezone.now())
    PeoplesChoiceStanding.objects.create(result=result, submission_snapshot_id=snapshot_id, votes=9, rank=1, winner=True)
    go_public(world)
    rows = [r for r in derived_achievements(leader) if r["kind"] == "peoples_choice"]
    assert [(r["rank"], r["prize_name"]) for r in rows] == [(1, "Crowd favourite")]
    Event.objects.filter(pk=world.event.pk).update(is_public=False)
    assert [r for r in derived_achievements(leader) if r["kind"] == "peoples_choice"] == []


def own_submission(world):  # noqa: F811
    submission = projects(world)[0]
    snapshot_id = world.snapshots[0]
    HackathonSubmission.objects.filter(pk=submission.pk).update(current_snapshot_id=snapshot_id)
    leader = User.objects.get(pk=world.ports.snaps[snapshot_id].member_ids[0])
    return submission, leader


def test_import_copies_only_the_callers_own_real_submission_once(world):  # noqa: F811
    submission, leader = own_submission(world)
    url = "/api/v1/member/profile/project-import"
    listed = client_for(leader).get(url)
    assert listed.status_code == 200
    assert [(row["id"], row["already_imported"]) for row in listed.data] == [(submission.pk, False)]
    stranger = User.objects.create_user(username="not-a-teammate")
    assert client_for(stranger).get(url).data == []
    assert client_for(stranger).post(url, {"submission_id": submission.pk}, format="json").status_code == 404
    created = client_for(leader).post(url, {"submission_id": submission.pk}, format="json")
    assert created.status_code == 201, created.data
    project = AccountProject.objects.get(pk=created.data["id"])
    assert project.source_submission_id == submission.pk and project.profile.user_id == leader.pk
    assert client_for(leader).post(url, {"submission_id": submission.pk}, format="json").status_code == 409
    assert client_for(leader).get(url).data[0]["already_imported"] is True
    # Removing the project frees the submission to be imported again.
    client_for(leader).put("/api/v1/member/profile", {"projects": []}, format="json")
    assert client_for(leader).post(url, {"submission_id": submission.pk}, format="json").status_code == 201


def test_a_submission_that_is_not_submitted_cannot_be_imported(world):  # noqa: F811
    submission, leader = own_submission(world)
    HackathonSubmission.objects.filter(pk=submission.pk).update(state="draft")
    response = client_for(leader).post(
        "/api/v1/member/profile/project-import", {"submission_id": submission.pk}, format="json")
    assert response.status_code == 404

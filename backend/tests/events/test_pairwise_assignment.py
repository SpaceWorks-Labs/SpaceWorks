"""Pairwise selection keeps the existing conflict, recusal, scope and >=3 coverage rules."""

import pytest
from django.http import Http404

from apps.events.judging.errors import ProgrammeError
from apps.events.judging.models_pairwise import JudgePairwiseComparison, JudgePairwiseCursor
from apps.events.judging.models_scoring import JudgeAssignment, JudgeConflict
from apps.events.judging.pairwise_projection import standings
from tests.events.pairwise_helpers import judge_command, judge_until_done, pairwise_round, pairwise_world

pytestmark = pytest.mark.django_db


def test_opening_seeds_one_cursor_and_a_first_project_per_judge_with_the_existing_notice(settings, monkeypatch):
    world = pairwise_world(settings, monkeypatch)
    round = pairwise_round(world)
    cursors = list(JudgePairwiseCursor.objects.filter(round=round).order_by("judge_id"))
    assert [c.judge_id for c in cursors] == sorted(world.roles)
    assert all(c.current.state == "assigned" and c.current.batch == "pairwise" and c.previous_id is None for c in cursors)
    from apps.events.judging.models_results import JudgingNotice
    notices = JudgingNotice.objects.filter(event=world.event, kind="judge_assigned")
    assert sorted(notices.values_list("source_id", flat=True)) == sorted(c.current_id for c in cursors)
    assert round.configuration["pairwise"]["seed"] == f"round-{round.pk}"
    assert round.algorithm_version == "spaceworks-pairwise-crowdbt-v1"


def test_every_judge_sees_each_project_once_and_coverage_reaches_min_reviews(settings, monkeypatch):
    world = pairwise_world(settings, monkeypatch, projects=4, judges=3)
    round = pairwise_round(world)
    for index in range(3):
        judge_until_done(world, round, index)
    for role in world.roles:
        seen = list(JudgeAssignment.objects.filter(round=round, judge_role_assignment_id=role)
                    .values_list("submission_snapshot_id", flat=True))
        assert sorted(seen) == sorted(world.snapshots)  # no project twice for one judge
    assert JudgePairwiseComparison.objects.filter(round=round).count() == 9
    result = standings(round)
    assert result["coverage_complete"] and all(row["n"] >= 3 for row in result["rows"])
    sequences = list(JudgePairwiseComparison.objects.filter(round=round).values_list("sequence", flat=True))
    assert sequences == list(range(1, 10))  # gapless replay order per round


def test_a_conflicted_team_is_never_shown_and_recusal_records_a_conflict(settings, monkeypatch):
    world = pairwise_world(settings, monkeypatch, projects=3, judges=1)
    round = pairwise_round(world)
    cursor = JudgePairwiseCursor.objects.get(round=round)
    first = cursor.current
    judge_command(world, 0, "recuse", round, reason="I mentored this team.")
    first.refresh_from_db()
    assert first.state == "recused"
    team_id = world.ports.snapshot(first.submission_snapshot_id).team_id
    assert JudgeConflict.objects.filter(round=round, member=world.judges[0], team_id=team_id, active=True).exists()
    judge_until_done(world, round, 0)
    shown = set(JudgeAssignment.objects.filter(round=round).exclude(pk=first.pk)
                .values_list("submission_snapshot_id", flat=True))
    assert first.submission_snapshot_id not in shown and len(shown) == 2


def test_room_and_track_scope_limit_what_a_judge_is_shown(settings, monkeypatch):
    world = pairwise_world(settings, monkeypatch, projects=3, judges=1)
    from dataclasses import replace
    role = world.roles[0]
    world.ports.judge_rows[role] = replace(world.ports.judge_rows[role], room="A")
    rooms = dict(zip(world.snapshots, ("A", "B", "A")))
    for pk, room in rooms.items():
        world.ports.snaps[pk] = replace(world.ports.snaps[pk], room=room)
    round = pairwise_round(world)
    judge_until_done(world, round, 0)
    shown = set(JudgeAssignment.objects.filter(round=round).values_list("submission_snapshot_id", flat=True))
    assert shown == {pk for pk, room in rooms.items() if room == "A"}


def test_a_stale_cursor_and_an_out_of_turn_command_are_refused(settings, monkeypatch):
    world = pairwise_world(settings, monkeypatch, projects=3, judges=1)
    round = pairwise_round(world)
    from apps.events.judging import pairwise_workflow
    from tests.events.pairwise_helpers import command
    with pytest.raises(ProgrammeError) as error:
        judge_command(world, 0, "compare", round, outcome="current")
    assert error.value.detail["code"] == "invalid_transition"  # nothing to compare yet
    judge_command(world, 0, "next", round)
    with pytest.raises(ProgrammeError) as error:
        pairwise_workflow.compare(world.event.pk, round.pk, actor=world.judges[0], data=command(0, outcome="current"))
    assert error.value.detail["code"] == "stale_version"
    assert not JudgePairwiseComparison.objects.exists()


def test_only_a_judge_of_this_event_may_use_a_cursor(settings, monkeypatch):
    world = pairwise_world(settings, monkeypatch, projects=2, judges=1)
    round = pairwise_round(world)
    from apps.events.judging import pairwise_workflow
    from tests.events.pairwise_helpers import command
    with pytest.raises(Http404):  # a full manager without a judge role has no cursor
        pairwise_workflow.next_project(world.event.pk, round.pk, actor=world.manager, data=command(0))

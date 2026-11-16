"""Pairwise invalidation, skip, replay and publish-once through the existing results workflow."""

import pytest

from apps.audit.models import AuditLog
from apps.events.judging import results_workflow
from apps.events.judging.boundary import mutation
from apps.events.judging.lifecycle import invalidate_snapshot_locked
from apps.events.judging.models_pairwise import JudgePairwiseComparison, JudgePairwiseCursor, JudgePairwiseInvalidation
from apps.events.judging.models_results import EventResultRound, ResultAnnouncement
from apps.events.judging.pairwise_projection import standings
from apps.events.judging.projections import round_calculation
from apps.events.judging.round_workflow import transition
from tests.events.pairwise_helpers import command, judge_command, judge_until_done, pairwise_round, pairwise_world

pytestmark = pytest.mark.django_db


def test_compare_and_skip_write_append_only_rows_and_audit_without_notes(settings, monkeypatch):
    world = pairwise_world(settings, monkeypatch, projects=4, judges=1)
    round = pairwise_round(world)
    judge_command(world, 0, "next", round)
    judge_command(world, 0, "compare", round, outcome="previous", notes="Private: cleaner wiring")
    judge_command(world, 0, "next", round)
    judge_command(world, 0, "skip", round)
    rows = list(JudgePairwiseComparison.objects.filter(round=round).order_by("sequence"))
    assert [row.outcome for row in rows] == ["previous", "skip"]
    assert rows[1].current.state == "skipped"
    compared = AuditLog.objects.get(action="event.programme.pairwise_compared")
    assert compared.meta["round_id"] == round.pk and compared.meta["sequence"] == 1 and "notes" not in compared.meta
    assert AuditLog.objects.filter(action="event.programme.pairwise_skipped").count() == 1
    assert "cleaner wiring" not in str(list(AuditLog.objects.values_list("meta", flat=True)))
    with pytest.raises(RuntimeError, match="append-only"):
        rows[0].outcome = "current"
        rows[0].save()
    # A skip is never a decisive comparison: one project counts once.
    assert sorted(row["n"] for row in standings(round)["rows"]) == [0, 0, 1, 1]


def test_invalidating_a_submission_drops_exactly_its_comparisons_from_the_replay(settings, monkeypatch):
    world = pairwise_world(settings, monkeypatch, projects=4, judges=2)
    round = pairwise_round(world)
    for index in range(2):
        judge_until_done(world, round, index)
    target = world.snapshots[0]
    touching = JudgePairwiseComparison.objects.filter(round=round).filter(
        previous__submission_snapshot_id=target) | JudgePairwiseComparison.objects.filter(
        round=round, current__submission_snapshot_id=target)
    expected = set(touching.values_list("pk", flat=True))
    before = {row["snapshot_id"]: row["n"] for row in standings(round)["rows"]}
    with mutation(world.event.pk, world.manager) as (event, locks):
        invalidate_snapshot_locked(event=event, snapshot_id=target, locks=locks, actor=world.manager)
    assert set(JudgePairwiseInvalidation.objects.values_list("comparison_id", flat=True)) == expected
    assert AuditLog.objects.filter(action="event.programme.pairwise_invalidated").count() == len(expected)
    after = {row["snapshot_id"]: row["n"] for row in standings(round)["rows"]}
    assert after[target] == 0 and sum(after.values()) == sum(before.values()) - 2 * len(expected)
    assert JudgePairwiseComparison.objects.count() == 6  # history is kept; only the replay drops rows


def test_a_finalized_pairwise_round_is_reproducible_and_publishes_once(settings, monkeypatch):
    world = pairwise_world(settings, monkeypatch, projects=3, judges=3)
    round = pairwise_round(world)
    for index in range(3):
        judge_until_done(world, round, index)
    round.refresh_from_db()
    for action in ("close", "finalize"):
        round.refresh_from_db()
        transition(world.event.pk, round.pk, actor=world.manager, action=action, data=command(round.version))
    round.refresh_from_db()
    calculation = round_calculation(round)
    assert calculation["algorithm_version"] == "spaceworks-pairwise-crowdbt-v1"
    assert calculation["parameters"]["alpha"] == 10.0 and calculation["coverage_complete"]
    assert calculation == round_calculation(round)  # a full replay, never a cached state
    result = results_workflow.finalize(world.event.pk, actor=world.manager,
                                       data=command(0, round_ids=[round.pk], integrity_reviewed=True))
    frozen = EventResultRound.objects.get(result_id=result["id"])
    assert frozen.calculation["rows"] == calculation["rows"]
    assert frozen.configuration["pairwise"]["gamma"] == 0.1
    data = command(result["version"], result_revision_id=result["id"])
    results_workflow.publish(world.event.pk, actor=world.manager, data=data)
    results_workflow.publish(world.event.pk, actor=world.manager, data=command(result["version"], result_revision_id=result["id"]))
    assert ResultAnnouncement.objects.filter(result_id=result["id"]).count() == 1


def test_a_round_open_or_closed_never_publishes_standings_on_its_own(settings, monkeypatch):
    world = pairwise_world(settings, monkeypatch, projects=3, judges=1)
    round = pairwise_round(world)
    judge_until_done(world, round, 0)
    assert not ResultAnnouncement.objects.exists()
    assert JudgePairwiseCursor.objects.get(round=round).current_id is None

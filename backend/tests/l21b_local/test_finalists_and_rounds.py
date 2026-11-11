"""L21b judging: finalists (preview, apply, publish), round settings, RANDOM, score-next and progress."""
from dataclasses import replace
from datetime import timedelta
from types import SimpleNamespace

import pytest
from django.utils import timezone

from apps.events.judging import finalists, progress
from apps.events.judging.errors import ProgrammeError
from apps.events.judging.models_definitions import JudgingRound
from apps.events.judging.models_finalists import FinalistAdvance, FinalistAnnouncement, JudgingFinalist
from apps.events.judging.models_scoring import JudgeAssignment, JudgeScore
from apps.events.judging.round_settings import random_plan
from tests.events.pairwise_helpers import command, pairwise_world

CRITERIA = [{"key": "impact", "label": "Impact", "weight": "1", "anchors": {str(i): f"level {i}" for i in range(1, 6)}}]


def enable(world, *keys):
    world.space.enabled_features = sorted(set(world.space.enabled_features) | set(keys))
    world.space.save(update_fields=["enabled_features"])


def weighted_round(world, key, *, open_round=True, **fields):
    from apps.events.judging.definitions_workflow import save_definition
    from apps.events.judging.round_workflow import transition
    saved = save_definition(world.event.pk, actor=world.manager, kind="judging-rounds",
                            data=command(key=key, mode="weighted_1_5", criteria=CRITERIA, **fields))
    if open_round:
        transition(world.event.pk, saved["id"], actor=world.manager, action="open", data=command(saved["version"]))
    return JudgingRound.objects.get(pk=saved["id"])


def assign_all(world, round, strategy="balanced", seed="0"):
    from apps.events.judging.round_workflow import assign
    round.refresh_from_db()
    return assign(world.event.pk, round.pk, actor=world.manager, data=command(
        round.version, judge_role_assignment_ids=world.roles, strategy=strategy, seed=seed))


def score_all(world, round, values):
    """Every judge scores every assignment; ``values`` maps snapshot id -> 1-5."""
    from apps.events.judging.scoring_workflow import score
    for row in JudgeAssignment.objects.filter(round=round, state="assigned").order_by("pk"):
        judge = world.judges[world.roles.index(row.judge_role_assignment_id)]
        score(world.event.pk, row.pk, actor=judge, data=command(row.version, scores={"impact": values[row.submission_snapshot_id]}))


def close_and_finalize(world, round):
    from apps.events.judging.round_workflow import transition
    for action in ("close", "finalize"):
        round.refresh_from_db()
        transition(world.event.pk, round.pk, actor=world.manager, action=action, data=command(round.version))
    round.refresh_from_db()


@pytest.fixture
def judged(settings, monkeypatch):
    world = pairwise_world(settings, monkeypatch, projects=4, judges=3, enabled=False)
    enable(world, "events.finalists")
    first = weighted_round(world, "heats")
    assign_all(world, first)
    score_all(world, first, dict(zip(world.snapshots, (5, 4, 3, 1))))
    close_and_finalize(world, first)
    second = weighted_round(world, "finals", open_round=False)
    return SimpleNamespace(world=world, first=first, second=second)


@pytest.mark.django_db
def test_top_n_preview_then_apply_advances_only_the_finalists(judged):
    w, first, second = judged.world, judged.first, judged.second
    params = {"source_round_id": first.pk, "target_round_id": second.pk, "selection": "top_n", "top_n": 2}
    plan = finalists.preview(w.event.pk, actor=w.manager, params=params)
    assert [row["snapshot_id"] for row in plan["finalists"]] == w.snapshots[:2]
    assert not FinalistAdvance.objects.exists()  # The preview writes nothing.
    second.refresh_from_db()
    finalists.apply(w.event.pk, actor=w.manager, data=command(second.version, fingerprint=plan["fingerprint"], **params))
    second.refresh_from_db()
    assert second.advanced_from_id == first.pk
    assert set(JudgingFinalist.objects.values_list("snapshot_id", flat=True)) == set(w.snapshots[:2])
    from apps.events.judging.round_workflow import transition
    transition(w.event.pk, second.pk, actor=w.manager, action="open", data=command(second.version))
    assert set(second.projects.values_list("snapshot_id", flat=True)) == set(w.snapshots[:2])


@pytest.mark.django_db
def test_a_stale_preview_refuses_with_plan_changed(judged):
    w, first, second = judged.world, judged.first, judged.second
    params = {"source_round_id": first.pk, "target_round_id": second.pk, "selection": "top_n", "top_n": 2}
    plan = finalists.preview(w.event.pk, actor=w.manager, params=params)
    w.ports.snaps[w.snapshots[0]] = replace(w.ports.snaps[w.snapshots[0]], eligible=False)  # disqualified meanwhile
    second.refresh_from_db()
    with pytest.raises(ProgrammeError) as error:
        finalists.apply(w.event.pk, actor=w.manager, data=command(second.version, fingerprint=plan["fingerprint"], **params))
    assert error.value.detail["code"] == "plan_changed"


@pytest.mark.django_db
def test_disqualified_and_withdrawn_projects_never_advance(judged):
    w, first, second = judged.world, judged.first, judged.second
    w.ports.snaps[w.snapshots[0]] = replace(w.ports.snaps[w.snapshots[0]], eligible=False)
    w.ports.snaps[w.snapshots[1]] = replace(w.ports.snaps[w.snapshots[1]], current=False)
    plan = finalists.preview(w.event.pk, actor=w.manager, params={
        "source_round_id": first.pk, "target_round_id": second.pk, "selection": "top_n", "top_n": 2})
    assert w.snapshots[0] not in [row["snapshot_id"] for row in plan["finalists"]]
    assert w.snapshots[1] not in [row["snapshot_id"] for row in plan["finalists"]]
    with pytest.raises(Exception):
        finalists.preview(w.event.pk, actor=w.manager, params={"source_round_id": first.pk, "target_round_id": second.pk,
                                                               "selection": "manual", "snapshot_ids": [w.snapshots[0]]})


@pytest.mark.django_db
def test_a_tie_at_the_cutoff_takes_every_tied_project(settings, monkeypatch):
    world = pairwise_world(settings, monkeypatch, projects=4, judges=3, enabled=False)
    enable(world, "events.finalists")
    first = weighted_round(world, "heats")
    assign_all(world, first)
    score_all(world, first, dict(zip(world.snapshots, (5, 4, 4, 1))))
    close_and_finalize(world, first)
    second = weighted_round(world, "finals", open_round=False)
    plan = finalists.preview(world.event.pk, actor=world.manager, params={
        "source_round_id": first.pk, "target_round_id": second.pk, "selection": "top_n", "top_n": 2})
    assert plan["tied_at_cutoff"] and len(plan["finalists"]) == 3


@pytest.mark.django_db
def test_publish_once_and_results_must_come_from_the_final_round(judged):
    from apps.events.judging.results_workflow import finalize
    w, first, second = judged.world, judged.first, judged.second
    params = {"source_round_id": first.pk, "target_round_id": second.pk, "selection": "top_n", "top_n": 2}
    plan = finalists.preview(w.event.pk, actor=w.manager, params=params)
    second.refresh_from_db()
    advance = finalists.apply(w.event.pk, actor=w.manager, data=command(second.version, fingerprint=plan["fingerprint"], **params))
    second.refresh_from_db()
    finalists.publish(w.event.pk, actor=w.manager, data=command(second.version, advance_id=advance["id"]))
    assert FinalistAnnouncement.objects.count() == 1
    with pytest.raises(ProgrammeError) as error:
        finalists.publish(w.event.pk, actor=w.manager, data=command(second.version, advance_id=advance["id"]))
    assert error.value.detail["code"] == "already_published"
    with pytest.raises(ProgrammeError):
        finalize(w.event.pk, actor=w.manager, data=command(0, round_ids=[first.pk], integrity_reviewed=True))


@pytest.mark.django_db
def test_finalists_switched_off_answer_404(judged):
    from django.http import Http404
    w = judged.world
    w.space.enabled_features = [key for key in w.space.enabled_features if key != "events.finalists"]
    w.space.save(update_fields=["enabled_features"])
    with pytest.raises(Http404):
        finalists.preview(w.event.pk, actor=w.manager, params={"source_round_id": judged.first.pk,
            "target_round_id": judged.second.pk, "selection": "top_n", "top_n": 1})


@pytest.mark.django_db
def test_finalist_certificates_follow_the_publication(judged):
    w, first, second = judged.world, judged.first, judged.second
    params = {"source_round_id": first.pk, "target_round_id": second.pk, "selection": "top_n", "top_n": 1}
    plan = finalists.preview(w.event.pk, actor=w.manager, params=params)
    second.refresh_from_db()
    advance = finalists.apply(w.event.pk, actor=w.manager, data=command(second.version, fingerprint=plan["fingerprint"], **params))
    member = w.ports.snaps[w.snapshots[0]].member_ids[0]
    assert not finalists.member_is_published_finalist(event_id=w.event.pk, member_id=member, advance_id=advance["id"], announcement_id=1)
    second.refresh_from_db()
    finalists.publish(w.event.pk, actor=w.manager, data=command(second.version, advance_id=advance["id"]))
    announcement = FinalistAnnouncement.objects.get()
    assert finalists.member_is_published_finalist(event_id=w.event.pk, member_id=member, advance_id=advance["id"],
                                                  announcement_id=announcement.pk)


@pytest.mark.django_db
def test_panel_limits_assignment_and_fresh_eyes_blocks_a_repeat_team(judged):
    w, first = judged.world, judged.first
    third = weighted_round(w, "repechage", open_round=False, panel=w.roles[:2], fresh_eyes=True)
    from apps.events.judging.round_workflow import transition
    transition(w.event.pk, third.pk, actor=w.manager, action="open", data=command(third.version))
    with pytest.raises(ProgrammeError):
        assign_all(w, third)  # the third judge is not on the panel
    from apps.events.judging.round_settings import fresh_eyes_blocked
    third.refresh_from_db()
    snaps = [w.ports.snaps[pk] for pk in w.snapshots]
    judges = [w.ports.judge_rows[pk] for pk in w.roles]
    assert fresh_eyes_blocked(third, snaps, judges)  # every judge scored teams in the heats
    assert third.configuration["settings"]["fresh_eyes"] is True


def test_random_strategy_is_reproducible_and_reroll_changes_it():
    one = random_plan([1, 2, 3, 4], [10, 11, 12, 13], target_views=3, blocked=set(), existing=set(), max_load=10, seed="a")
    again = random_plan([1, 2, 3, 4], [10, 11, 12, 13], target_views=3, blocked=set(), existing=set(), max_load=10, seed="a")
    other = random_plan([1, 2, 3, 4], [10, 11, 12, 13], target_views=3, blocked=set(), existing=set(), max_load=10, seed="b")
    assert one == again and not one.deficits
    assert one.pairs != other.pairs or one.loads != other.loads
    short = random_plan([1, 2], [10, 11, 12], target_views=3, blocked={(1, 10)}, existing=set(), max_load=10, seed="a")
    assert short.deficits == {1: 1}
    with pytest.raises(ValueError):
        random_plan([1], [10], target_views=2, blocked=set(), existing=set(), max_load=10, seed="a")


def _scored(judge, snapshot, value):
    score = SimpleNamespace(submitted_at=timezone.now(), criterion_values={"impact": value})
    return SimpleNamespace(judge_role_assignment_id=judge, submission_snapshot_id=snapshot, score=score)


def test_outliers_flag_two_sd_and_a_25_point_spread():
    round = SimpleNamespace(mode="weighted_1_5", configuration={"criteria": CRITERIA})
    rows = progress._outliers(round, [_scored(1, 9, 5), _scored(2, 9, 2)])
    assert {(row["judge_role_assignment_id"], row["rule"]) for row in rows} == {(1, "spread_25"), (2, "spread_25")}
    calm = progress._outliers(round, [_scored(1, 9, 4), _scored(2, 9, 4), _scored(3, 9, 4)])
    assert calm == []
    sd_rows = progress._outliers(round, [_scored(j, 9, 3) for j in range(1, 10)] + [_scored(99, 9, 5)])
    assert any(row["judge_role_assignment_id"] == 99 and row["rule"] == "two_sd" for row in sd_rows)


@pytest.mark.django_db
def test_progress_reports_below_target_completion_and_stale_drafts(settings, monkeypatch):
    world = pairwise_world(settings, monkeypatch, projects=3, judges=3, enabled=False)
    round = weighted_round(world, "heats")
    assign_all(world, round)
    from apps.events.judging.scoring_workflow import score
    row = JudgeAssignment.objects.filter(round=round).order_by("pk").first()
    judge = world.judges[world.roles.index(row.judge_role_assignment_id)]
    score(world.event.pk, row.pk, actor=judge, data=command(row.version, scores={"impact": 3}, submit=False))
    JudgeScore.objects.filter(assignment=row).update(saved_at=timezone.now() - timedelta(hours=30))
    report = progress.report(world.event.pk, round.pk, actor=world.manager)
    assert {item["snapshot_id"] for item in report["below_target"]} == set(world.snapshots)
    assert [item["assignment_id"] for item in report["stale_drafts"]] == [row.pk]
    assert all(item["completion"] == 0 for item in report["judges"])


@pytest.mark.django_db
def test_score_next_prefers_a_started_project_then_the_fewest_reviews(settings, monkeypatch):
    world = pairwise_world(settings, monkeypatch, projects=3, judges=3, enabled=False)
    round = weighted_round(world, "heats")
    assign_all(world, round)
    judge, role = world.judges[0], world.roles[0]
    mine = list(JudgeAssignment.objects.filter(round=round, judge_role_assignment_id=role).order_by("pk"))
    picked = progress.next_project(world.event.pk, round.pk, actor=judge, data=command(0))
    assert picked["reason"] == "fewest_reviews" and picked["assignment_id"] in {row.pk for row in mine}
    from apps.events.judging.scoring_workflow import score
    target = mine[-1]
    score(world.event.pk, target.pk, actor=judge, data=command(target.version, scores={"impact": 4}, submit=False))
    again = progress.next_project(world.event.pk, round.pk, actor=judge, data=command(0))
    assert again == {"assignment_id": target.pk, "snapshot_id": target.submission_snapshot_id, "reason": "started"}


@pytest.mark.django_db
def test_visibility_all_lets_a_judge_pull_an_unassigned_project(settings, monkeypatch):
    world = pairwise_world(settings, monkeypatch, projects=3, judges=3, enabled=False)
    round = weighted_round(world, "open-floor", visibility="all")
    judge = world.judges[0]
    pulled = progress.next_project(world.event.pk, round.pk, actor=judge, data=command(0))
    row = JudgeAssignment.objects.get(pk=pulled["assignment_id"])
    assert row.batch == "pull" and row.judge_role_assignment_id == world.roles[0]

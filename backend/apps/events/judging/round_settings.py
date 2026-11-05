"""L21b per-round settings: the optional panel, fresh eyes, and the seeded RANDOM strategy.

Settings are edited only while a round is a draft (the definition writer refuses later edits) and are
frozen into the round configuration when it opens.
"""

from hashlib import sha256

from django.http import Http404

from .assignment_planner import AssignmentPlan
from .models_definitions import JudgingPanelSeat
from .models_scoring import JudgeAssignment
from .ports import runtime


def replace_panel(event, round, judge_ids):
    """Rewrite a draft round's panel. Every seat must be a judge role of this event."""
    judges = [runtime().judge(pk) for pk in judge_ids]
    if any(judge.event_id != event.pk for judge in judges):
        raise Http404
    JudgingPanelSeat.objects.filter(round=round).delete()
    for pk in sorted(judge_ids):
        JudgingPanelSeat.objects.create(round=round, judge_role_assignment_id=pk)


def panel_ids(round):
    """The panel's judge role IDs, or None when the round has no panel (every active judge)."""
    ids = set(round.panel_seats.values_list("judge_role_assignment_id", flat=True))
    return ids or None


def frozen_settings(round):
    return {"visibility": round.visibility, "fresh_eyes": round.fresh_eyes,
            "panel": sorted(panel_ids(round) or ()), "advanced_from_id": round.advanced_from_id,
            "submission_stage_id": round.submission_stage_id}


def prior_reviews(round):
    """(member_id, team_id) pairs already reviewed in an EARLIER round of this event (fresh eyes)."""
    rows = JudgeAssignment.objects.filter(event_id=round.event_id, state="scored").exclude(round_id=round.pk)
    if round.pk:
        rows = rows.filter(round_id__lt=round.pk)
    seen = set()
    for judge_id, snapshot_id in rows.values_list("judge_role_assignment_id", "submission_snapshot_id").distinct():
        seen.add((runtime().judge(judge_id).member_id, runtime().snapshot(snapshot_id).team_id))
    return seen


def fresh_eyes_blocked(round, snapshots, judges):
    """Pairs a fresh-eyes round may never assign: a judge meeting a team they already reviewed."""
    if not round.fresh_eyes:
        return set()
    seen = prior_reviews(round)
    return {(s.id, j.role_assignment_id) for s in snapshots for j in judges if (j.member_id, s.team_id) in seen}


def random_plan(snapshot_ids, judge_ids, *, target_views, blocked, existing, max_load, seed):
    """Seeded RANDOM strategy: each project takes judges in sha256(seed:project:judge) order.

    The same seed always gives the same plan, so a preview can be applied exactly; Re-roll is a new seed.
    """
    projects, judges = sorted(set(snapshot_ids)), sorted(set(judge_ids))
    if type(target_views) is not int or not 3 <= target_views <= 20 or not 1 <= max_load <= 2000:
        raise ValueError("Assignment limits exceeded.")
    if len(projects) > 2000 or len(judges) > 500:
        raise ValueError("Assignment limits exceeded.")
    loads = {judge: sum(j == judge for _, j in existing) for judge in judges}
    pairs, deficits = [], {}
    ordered_projects = sorted(projects, key=lambda p: sha256(f"{seed}:{p}".encode()).digest())
    for project in ordered_projects:
        needed = max(0, target_views - sum(p == project for p, _ in existing))
        for judge in sorted(judges, key=lambda j: sha256(f"{seed}:{project}:{j}".encode()).digest()):
            if not needed:
                break
            pair = (project, judge)
            if pair in blocked or pair in existing or loads[judge] >= max_load:
                continue
            pairs.append(pair)
            loads[judge] += 1
            needed -= 1
        if needed:
            deficits[project] = needed
    return AssignmentPlan(tuple(sorted(pairs)), deficits, loads)

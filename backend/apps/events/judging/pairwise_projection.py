"""Derived pairwise reads: valid comparisons, round calculation, judge cursor view, standings.

State is never trusted: every read replays the valid comparisons in sequence order. A comparison
is valid while it has no invalidation row, both of its assignments are still `scored`, and both
projects are still current, eligible and nonconflicted for that judge (`conflicts.eligible`).
"""

from django.utils.translation import gettext
from django.http import Http404

from apps.makerspaces.platform import feature_enabled
from .conflicts import eligible
from .errors import ProgrammeError
from .models_pairwise import JudgePairwiseComparison, JudgePairwiseCursor
from .pairwise_ranking import DEFAULTS, Comparison, pairwise_results, replay
from .ports import runtime

BATCH = "pairwise"
FEATURE = "events.pairwise_judging"


def pairwise_enabled(event):
    return feature_enabled(event.makerspace, FEATURE)


def require_pairwise(event, *, hide=True):
    """Off means no pairwise route exists (404); definition and round commands refuse with 403."""
    if not pairwise_enabled(event):
        if hide:
            raise Http404
        raise ProgrammeError("feature_disabled", gettext("Pairwise judging is switched off for this space."), status=403)


def parameters(round):
    return {**DEFAULTS, **round.configuration.get("pairwise", {})}


def _eligibility(round, snapshots):
    cache, judges = {}, {}

    def ok(judge_id, snapshot_id):
        key = (judge_id, snapshot_id)
        if key not in cache:
            judge = judges.setdefault(judge_id, runtime().judge(judge_id))
            snapshot = snapshots.get(snapshot_id)
            cache[key] = bool(snapshot) and eligible(judge, snapshot, round)
        return cache[key]
    return ok


def valid_comparisons(round, snapshots):
    """Decisive comparisons that still count, in replay order, as pure `Comparison` values."""
    ok = _eligibility(round, snapshots)
    rows = (JudgePairwiseComparison.objects.filter(round=round, invalidation__isnull=True)
            .exclude(outcome="skip").select_related("previous", "current").order_by("sequence"))
    result = []
    for row in rows:
        before, now = row.previous, row.current
        if before.state != "scored" or now.state != "scored":
            continue
        if not (ok(row.judge_id, before.submission_snapshot_id) and ok(row.judge_id, now.submission_snapshot_id)):
            continue
        pair = (before.submission_snapshot_id, now.submission_snapshot_id)
        winner, loser = pair if row.outcome == "previous" else pair[::-1]
        result.append(Comparison(row.judge_id, winner, loser))
    return result


def pairwise_calculation(round, snapshots):
    params = parameters(round)
    comparisons = valid_comparisons(round, snapshots)
    rows = pairwise_results(snapshots, comparisons, params, min_reviews=round.configuration["min_reviews"])
    return {"algorithm_version": round.algorithm_version, "parameters": params, "rows": rows,
            "coverage_complete": bool(rows) and all(row["coverage_complete"] for row in rows)}


def selection_state(round, snapshots):
    comparisons = valid_comparisons(round, snapshots)
    counts = {}
    for comparison in comparisons:
        for pk in (comparison.winner, comparison.loser):
            counts[pk] = counts.get(pk, 0) + 1
    return replay(comparisons, parameters(round)), counts


def live_snapshots(round):
    ports = runtime()
    found = {pk: ports.snapshot(pk) for pk in round.projects.values_list("snapshot_id", flat=True)}
    return {pk: s for pk, s in found.items() if s.event_id == round.event_id and s.eligible and s.current}


def card(assignment):
    snapshot = runtime().snapshot(assignment.submission_snapshot_id)
    return {"assignment_id": assignment.pk, "snapshot_id": snapshot.id, "title": snapshot.title,
            "description": snapshot.description, "track_id": assignment.track_id,
            "asset_ids": list(snapshot.judge_asset_ids)}


def standings(round):
    """Organiser-only live view; never shown to judges (anchoring)."""
    snapshots = live_snapshots(round)
    calculation = pairwise_calculation(round, snapshots) if round.configuration else {"rows": [], "coverage_complete": False}
    judges = {}
    for row in JudgePairwiseComparison.objects.filter(round=round).order_by("sequence").values("judge_id", "outcome"):
        entry = judges.setdefault(row["judge_id"], {"judge_role_assignment_id": row["judge_id"], "compared": 0, "skipped": 0})
        entry["skipped" if row["outcome"] == "skip" else "compared"] += 1
    cursors = JudgePairwiseCursor.objects.filter(round=round).values_list("judge_id", flat=True)
    for judge_id in cursors:
        judges.setdefault(judge_id, {"judge_role_assignment_id": judge_id, "compared": 0, "skipped": 0})
    return {"round_id": round.pk, "event_id": round.event_id, "algorithm_version": round.algorithm_version,
            "coverage_complete": calculation["coverage_complete"], "rows": calculation["rows"],
            "judges": [judges[key] for key in sorted(judges)]}

"""Live eligibility filtered private calculations and read-only F summaries."""

from decimal import Decimal

from .calculations import ALGORITHM_VERSION, Ballot, Criterion, Judgment, estimate_judges, top3_results, weighted_results
from .conflicts import eligible
from .models_definitions import JudgingRound
from .models_scoring import JudgeAssignment, JudgeRankingBallot, JudgeScore
from .ports import runtime


def round_calculation(round):
    ports = runtime()
    snapshots = {pk: ports.snapshot(pk) for pk in round.projects.values_list("snapshot_id", flat=True)}
    snapshots = {pk: snapshot for pk, snapshot in snapshots.items()
                 if snapshot.event_id == round.event_id and snapshot.eligible and snapshot.current}
    assignments = list(JudgeAssignment.objects.filter(round=round, state="scored").order_by("pk"))
    judges = {pk: ports.judge(pk) for pk in {a.judge_role_assignment_id for a in assignments}}
    valid = {a.pk: a for a in assignments if a.submission_snapshot_id in snapshots
             and eligible(judges[a.judge_role_assignment_id], snapshots[a.submission_snapshot_id], round)}
    config = round.configuration
    if not config or round.state == "draft":  # A pairwise draft keeps only its unfrozen settings here.
        return {"algorithm_version": ALGORITHM_VERSION, "rows": [], "coverage_complete": False}
    if round.mode == "pairwise":
        from .pairwise_projection import pairwise_calculation
        return pairwise_calculation(round, snapshots)
    if round.mode == "weighted_1_5":
        criteria = [Criterion(row["key"], Decimal(row["weight"])) for row in config["criteria"]]
        scores = JudgeScore.objects.filter(assignment_id__in=valid, submitted_at__isnull=False).order_by("pk")
        judgments = [Judgment(valid[s.assignment_id].submission_snapshot_id,
                              judges[valid[s.assignment_id].judge_role_assignment_id].member_id,
                              s.criterion_values) for s in scores]
        rows = weighted_results(snapshots, judgments, criteria, min_reviews=config["min_reviews"],
                                normalization=config["normalization"])
    else:
        ballots = []
        for ballot in JudgeRankingBallot.objects.filter(round=round).prefetch_related("choices").order_by("pk"):
            choices = list(ballot.choices.all())
            # Any revoked/conflicted/superseded exposure invalidates the complete ballot's six-point budget.
            if not choices or any(choice.assignment_id not in valid for choice in choices):
                continue
            exposed = tuple(valid[c.assignment_id].submission_snapshot_id for c in choices)
            ranked = tuple(valid[c.assignment_id].submission_snapshot_id for c in
                           sorted((c for c in choices if c.rank), key=lambda c: c.rank))
            ballots.append(Ballot(judges[ballot.judge_id].member_id, ballot.batch, exposed, ranked))
        rows = top3_results(snapshots, ballots, min_reviews=config["min_reviews"])
    return {"algorithm_version": round.algorithm_version, "rows": rows,
            "coverage_complete": bool(rows) and all(row["coverage_complete"] for row in rows)}


def progress(round, *, actor=None):
    calculation = round_calculation(round)
    assignments = round.assignments.all()
    actions = []
    if actor is not None:
        from apps.events import event_authority
        if event_authority.can(actor, round.event, "manage_hackathon"):
            actions = {"draft": ["edit", "open"], "open": ["close"] if round.mode == "pairwise" else ["assign", "close"]}.get(round.state, [])
        if round.state == "closed" and event_authority.can(actor, round.event, None):
            actions = ["finalize"]
    return {"id": round.pk, "event_id": round.event_id, "version": round.version,
            "state": round.state, "mode": round.mode, "key": round.key, "min_reviews": round.min_reviews,
            "normalization": round.normalization, "opens_at": round.opens_at, "closes_at": round.closes_at,
            "criteria": list(round.criteria.values("key", "label", "weight", "anchors")),
            "minutes_per_view": round.minutes_per_view, "judging_minutes": round.judging_minutes,
            # Pairwise: the first view of each judge is not a comparison, so plan one extra view per project.
            "estimated_judges": estimate_judges(round.projects.count(), round.min_reviews + (round.mode == "pairwise"),
                                                round.minutes_per_view, round.judging_minutes),
            "guidance": (round.configuration or {}).get("guidance", ""),
            "exploration": (round.configuration or {}).get("pairwise", {}).get("exploration"),
            "allowed_actions": actions, "assigned": assignments.filter(state__in=("assigned", "scored")).count(),
            "submitted": sum(row["n"] for row in calculation["rows"]),
            "recused": assignments.filter(state="recused").count(),
            "skipped": assignments.filter(state="skipped").count(), "visibility": round.visibility,
            "fresh_eyes": round.fresh_eyes, "advanced_from_id": round.advanced_from_id,
            "panel": list(round.panel_seats.order_by("judge_role_assignment_id").values_list("judge_role_assignment_id", flat=True)),
            **calculation}


def summary(event_id, *, actor):
    from apps.events import event_authority
    from apps.events.models import Event
    event = Event.objects.get(pk=event_id)
    if not event_authority.can(actor, event, "manage_hackathon"):
        return {}  # Readiness must not disclose unauthorized counts.
    rounds = [progress(row) for row in JudgingRound.objects.filter(event_id=event_id).order_by("pk")]
    return {"rounds": len(rounds), "coverage_complete": bool(rounds) and all(r["coverage_complete"] for r in rounds),
            "assignments": sum(r["assigned"] for r in rounds), "submitted": sum(r["submitted"] for r in rounds)}

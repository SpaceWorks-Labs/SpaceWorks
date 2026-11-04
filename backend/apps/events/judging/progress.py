"""L21b judging operations: the organizer's progress view and a judge's "Score next project".

Progress reads the live round (never a cache): projects below the review target, per-judge
completion, outlier scores and drafts saved but not submitted for more than a day. Score-next picks
a project the judge already started, else the eligible project with the fewest reviews. With round
visibility "all", a judge (on the panel, when there is one) may pull an unassigned project; the
assignment is then created exactly as a planned one would be.
"""

from datetime import timedelta
from decimal import Decimal
from statistics import mean, pstdev

from django.http import Http404
from django.utils import timezone

from .boundary import command, mutation, notice, owned
from .calculations import Criterion, weighted_value
from .conflicts import eligible
from .errors import invalid
from .models_definitions import JudgingRound
from .models_scoring import JudgeAssignment, JudgeScore
from .ports import runtime
from .projections import round_calculation
from .round_settings import panel_ids, prior_reviews
from .serializers import CommandInput, validated

STALE_AFTER = timedelta(hours=24)
SPREAD_POINTS = Decimal("25")


def _points(value):
    return (value - 1) * 25  # weighted 1-5 value on a 0-100 scale


def _outliers(round, scored):
    if round.mode != "weighted_1_5" or not (round.configuration or {}).get("criteria"):
        return []
    criteria = [Criterion(c["key"], Decimal(c["weight"])) for c in round.configuration["criteria"]]
    by_project = {}
    for assignment in scored:
        score = getattr(assignment, "score", None)
        if score is None or score.submitted_at is None:
            continue
        try:
            value = _points(weighted_value(score.criterion_values, criteria))
        except ValueError:
            continue
        by_project.setdefault(assignment.submission_snapshot_id, []).append((assignment, value))
    rows = []
    for snapshot_id, pairs in by_project.items():
        values = [value for _, value in pairs]
        if len(values) < 2:
            continue
        centre, spread = mean(values), max(values) - min(values)
        sd = pstdev(values) if len(values) >= 3 else Decimal(0)
        for assignment, value in pairs:
            rule = "two_sd" if sd and abs(value - centre) > 2 * sd else (
                "spread_25" if spread > SPREAD_POINTS and value in (max(values), min(values)) else None)
            if rule:
                rows.append({"snapshot_id": snapshot_id, "judge_role_assignment_id": assignment.judge_role_assignment_id,
                             "score": str(round_points(value)), "project_mean": str(round_points(centre)), "rule": rule})
    return rows


def round_points(value):
    return Decimal(value).quantize(Decimal("0.01"))


def report(event_id, round_id, *, actor):
    from apps.events import event_authority
    event = event_authority.get_event(actor, event_id, "manage_hackathon")
    runtime().require_programme(event)
    round = JudgingRound.objects.filter(event=event, pk=round_id).first()
    if round is None:
        raise Http404
    calculation = round_calculation(round)
    reviews = {row["snapshot_id"]: row["n"] for row in calculation["rows"]}
    target = round.min_reviews
    below = []
    for snapshot_id in round.projects.order_by("snapshot_id").values_list("snapshot_id", flat=True):
        snapshot = runtime().snapshot(snapshot_id)
        if snapshot.current and snapshot.eligible and reviews.get(snapshot_id, 0) < target:
            below.append({"snapshot_id": snapshot_id, "title": snapshot.title,
                          "reviews": reviews.get(snapshot_id, 0), "target": target})
    assignments = list(round.assignments.select_related("score").order_by("pk"))
    judges = {}
    for row in assignments:
        entry = judges.setdefault(row.judge_role_assignment_id, {"assigned": 0, "submitted": 0, "withdrawn": 0})
        if row.state in ("assigned", "scored"):
            entry["assigned"] += 1
        if row.state == "scored":
            entry["submitted"] += 1
        if row.state in ("recused", "skipped"):
            entry["withdrawn"] += 1
    from apps.accounts.pii_presentation import MASK, pii_visible
    names = _judge_names(judges) if pii_visible(actor, event.makerspace_id) else {pk: MASK for pk in judges}
    judge_rows = [{"judge_role_assignment_id": pk, "name": names.get(pk, ""), **counts,
                   "completion": int(100 * counts["submitted"] / counts["assigned"]) if counts["assigned"] else 0}
                  for pk, counts in sorted(judges.items())]
    cutoff = timezone.now() - STALE_AFTER
    stale = [{"assignment_id": row.pk, "judge_role_assignment_id": row.judge_role_assignment_id,
              "snapshot_id": row.submission_snapshot_id, "saved_at": row.score.saved_at}
             for row in assignments if row.state == "assigned" and hasattr(row, "score")
             and row.score.submitted_at is None and row.score.saved_at and row.score.saved_at < cutoff]
    return {"round_id": round.pk, "state": round.state, "mode": round.mode, "target": target,
            "below_target": below, "judges": judge_rows,
            "outliers": _outliers(round, [a for a in assignments if a.state == "scored"]), "stale_drafts": stale}


def _judge_names(judges):
    from apps.accounts.models import User
    members = {pk: runtime().judge(pk).member_id for pk in judges}
    users = {u.pk: u.display_name or u.username for u in User.objects.filter(pk__in=set(members.values()))}
    return {pk: users.get(member, "") for pk, member in members.items()}


def next_project(event_id, round_id, *, actor, data):
    values = validated(CommandInput, data)
    with mutation(event_id, actor, permission="judge", account_ids=(actor.pk,)) as (event, _):
        def run():
            round = owned(JudgingRound, event_id, round_id)  # Judges never read round versions; send 0.
            round.event = event
            now = timezone.now()
            if (round.state != "open" or round.mode != "weighted_1_5" or (round.opens_at and now < round.opens_at)
                    or (round.closes_at and now >= round.closes_at)):
                invalid("Score next works in an open weighted round.")
            judge = _own_judge(event_id, actor, round)
            mine = list(JudgeAssignment.objects.filter(round=round, judge_role_assignment_id=judge.role_assignment_id))
            live = [a for a in mine if a.state == "assigned"
                    and eligible(judge, runtime().snapshot(a.submission_snapshot_id), round)]
            started = sorted((a for a in live if JudgeScore.objects.filter(assignment=a).exists()), key=lambda a: a.pk)
            if started:
                return _pick(started[0], "started")
            counts = _review_counts(round)
            candidates = [(counts.get(a.submission_snapshot_id, 0), a.submission_snapshot_id, a) for a in live]
            if round.visibility == "all":
                taken = {a.submission_snapshot_id for a in mine}
                seen = prior_reviews(round) if round.fresh_eyes else set()
                for snapshot_id in round.projects.values_list("snapshot_id", flat=True):
                    snapshot = runtime().snapshot(snapshot_id)
                    if (snapshot_id not in taken and eligible(judge, snapshot, round)
                            and (judge.member_id, snapshot.team_id) not in seen):
                        candidates.append((counts.get(snapshot_id, 0), snapshot_id, None))
            if not candidates:
                return {"assignment_id": None, "snapshot_id": None, "reason": "none"}
            _, snapshot_id, assignment = min(candidates, key=lambda c: (c[0], c[1]))
            if assignment is None:
                snapshot = runtime().snapshot(snapshot_id)
                assignment = JudgeAssignment.objects.create(event=event, round=round, batch="pull", room=snapshot.room,
                    judge_role_assignment_id=judge.role_assignment_id, submission_snapshot_id=snapshot_id,
                    track_id=min(set(snapshot.track_ids) & set(judge.track_ids or snapshot.track_ids), default=None))
                notice(event, "judge_assigned", assignment.pk, assignment.version)
            return _pick(assignment, "fewest_reviews")
        return command(event, actor, values, path=f"judging-rounds/{round_id}/next-project", run=run)


def _pick(assignment, reason):
    return {"assignment_id": assignment.pk, "snapshot_id": assignment.submission_snapshot_id, "reason": reason}


def _own_judge(event_id, actor, round):
    panel = panel_ids(round)
    for judge in runtime().judges(event_id):
        if judge.member_id == actor.pk and judge.active and (panel is None or judge.role_assignment_id in panel):
            return judge
    raise Http404


def _review_counts(round):
    counts = {}
    for snapshot_id in JudgeAssignment.objects.filter(round=round, state__in=("assigned", "scored")).values_list(
            "submission_snapshot_id", flat=True):
        counts[snapshot_id] = counts.get(snapshot_id, 0) + 1
    return counts

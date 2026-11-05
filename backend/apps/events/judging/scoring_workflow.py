"""Only assigned judges submit their own drafts, ballots, skips or recusals."""

from decimal import Decimal

from django.http import Http404
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from .boundary import audit, changed, command, envelope, mutation, owned
from .ballot_invalidation import invalidate_pairwise_locked, invalidate_peers_locked
from .calculations import Criterion, top3_points, weighted_value
from .conflicts import require_assignment
from .errors import invalid
from .models_definitions import JudgingRound
from .models_scoring import (
    JudgeAssignment, JudgeConflict, JudgeRankingBallot, JudgeRankingChoice, JudgeScore, JudgingReason,
)
from .ports import runtime
from .serializers import RankInput, ReasonInput, ScoreInput, validated


def _locked_assignment(event_id, assignment_id, expected):
    # Resolve parent without locking, then lock round→assignment. Event already serialized scope.
    parent_id = JudgeAssignment.objects.filter(event_id=event_id, pk=assignment_id).values_list("round_id", flat=True).first()
    if parent_id is None:
        raise Http404
    round = owned(JudgingRound, event_id, parent_id)
    assignment = owned(JudgeAssignment, event_id, assignment_id, expected=expected)
    round.event_id = event_id
    return round, assignment


def _open(round):
    now = timezone.now()
    if round.state != "open" or (round.opens_at and now < round.opens_at) or (round.closes_at and now >= round.closes_at):
        invalid("This judging round is closed.")


def score(event_id, assignment_id, *, actor, data):
    values = validated(ScoreInput, data)
    with mutation(event_id, actor, permission="judge", account_ids=(actor.pk,)) as (event, locks):
        def run():
            round, assignment = _locked_assignment(event_id, assignment_id, values["expected_version"])
            round.event = event
            require_assignment(actor, assignment, round)
            _open(round)
            if round.mode != "weighted_1_5" or assignment.state != "assigned":
                invalid()
            criteria = [Criterion(c["key"], Decimal(c["weight"])) for c in round.configuration["criteria"]]
            try:
                if values["submit"]:
                    weighted_value(values.get("scores", {}), criteria)
                elif not set(values.get("scores", {})) <= {c.key for c in criteria}:
                    raise ValueError("Use only the frozen criterion keys.")
            except ValueError as exc:
                raise ValidationError({"scores": str(exc)}) from exc
            row = JudgeScore.objects.filter(assignment=assignment).first()
            if row is None:
                row = JudgeScore(event=event, assignment=assignment, makerspace_id=event.makerspace_id)
            else:
                row.version += 1
            row.criterion_values = values.get("scores", {})
            row.notes = values["notes"]
            if "team_feedback" in values:  # S4: kept apart from the private notes.
                row.team_feedback = values["team_feedback"]
            row.saved_at = timezone.now()
            row.submitted_at = row.saved_at if values["submit"] else None
            row.save()
            if values["submit"]:
                assignment.state = "scored"
            return changed(event, actor, "score_submitted" if values["submit"] else "score_draft_saved", assignment)
        return command(event, actor, values, path=f"judge-assignments/{assignment_id}/score", run=run)


def rank(event_id, assignment_id, *, actor, data):
    values = validated(RankInput, data)
    with mutation(event_id, actor, permission="judge") as (event, _):
        def run():
            round, assignment = _locked_assignment(event_id, assignment_id, values["expected_version"])
            round.event = event
            require_assignment(actor, assignment, round)
            _open(round)
            if round.mode != "top3" or assignment.state != "assigned":
                invalid()
            rows = list(round.assignments.select_for_update().filter(
                judge_role_assignment_id=assignment.judge_role_assignment_id, batch=assignment.batch).order_by("pk"))
            rows = [row for row in rows if row.state == "assigned"]
            for row in rows:
                require_assignment(actor, row, round)
            snapshots = tuple(row.submission_snapshot_id for row in rows)
            try:
                top3_points(snapshots, tuple(values["ordered_top3"]))
            except ValueError as exc:
                raise ValidationError({"ordered_top3": str(exc)}) from exc
            if JudgeRankingBallot.objects.filter(round=round, judge_id=assignment.judge_role_assignment_id,
                                                 batch=assignment.batch).exists():
                invalid("This batch already has a submitted ballot.")
            ballot = JudgeRankingBallot.objects.create(event=event, round=round,
                judge_id=assignment.judge_role_assignment_id, batch=assignment.batch, submitted_at=timezone.now())
            for row in rows:
                rank_value = (values["ordered_top3"].index(row.submission_snapshot_id) + 1
                              if row.submission_snapshot_id in values["ordered_top3"] else None)
                JudgeRankingChoice.objects.create(ballot=ballot, assignment=row, rank=rank_value)
                row.state = "scored"
                row.version += 1
                row.save()
            audit(event, actor, "ranking_submitted", ballot, count=len(rows), round_id=round.pk)
            return envelope(assignment, ballot_id=ballot.pk)
        return command(event, actor, values, path=f"judge-assignments/{assignment_id}/rank", run=run)


def recuse_or_skip(event_id, assignment_id, *, actor, action, data):
    if action not in ("recuse", "skip"):
        raise ValueError("Unknown judging action.")
    values = validated(ReasonInput, data)
    with mutation(event_id, actor, permission="judge", account_ids=(actor.pk,)) as (event, locks):
        def run():
            round, assignment = _locked_assignment(event_id, assignment_id, values["expected_version"])
            return withdraw_locked(event, actor, round, assignment, action=action, text=values["reason"], locks=locks)
        return command(event, actor, values, path=f"judge-assignments/{assignment_id}/{action}", run=run)


def withdraw_locked(event, actor, round, assignment, *, action, text, locks):
    """Recuse or skip one locked assignment; shared by the assignment and pairwise routes."""
    judge = runtime().judge(assignment.judge_role_assignment_id)
    if judge.member_id != actor.pk or judge.event_id != event.pk or not judge.active:
        raise Http404
    _open(round)
    if assignment.state not in ("assigned", "scored"):
        invalid()
    reason = JudgingReason.objects.create(event=event, makerspace_id=event.makerspace_id,
                                          actor=actor, body=text)
    if round.mode == "top3":
        invalidate_peers_locked(event=event, actor=actor, assignment=assignment, locks=locks)
    elif round.mode == "pairwise":
        invalidate_pairwise_locked(event=event, actor=actor, assignment=assignment, reason=reason, locks=locks)
    assignment.state = "recused" if action == "recuse" else "skipped"
    assignment.reason = reason
    if action == "recuse":
        snapshot = runtime().snapshot(assignment.submission_snapshot_id)
        conflict, created = JudgeConflict.objects.get_or_create(event=event, round=round, member=actor,
            team_id=snapshot.team_id, defaults={"reason": reason})
        if not created and not conflict.active:
            conflict.active = True
            conflict.reason = reason
            conflict.version += 1
            conflict.save()
    return changed(event, actor, f"judge_{action}", assignment)

"""Assignments and submitted judgments. Mutable score drafts never enter totals."""

from django.conf import settings
from django.db import models

from apps.encryption.mappers import ScopedPiiModelMixin
from .models_base import AppendOnly, EventOwned, PrivateRecord


class JudgingReason(ScopedPiiModelMixin, PrivateRecord, AppendOnly):
    event = models.ForeignKey("events.Event", on_delete=models.CASCADE, related_name="+")
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    body = models.TextField(max_length=2000)
    created_at = models.DateTimeField(auto_now_add=True)


class JudgeAssignment(EventOwned):
    round = models.ForeignKey("events.JudgingRound", on_delete=models.CASCADE, related_name="assignments")
    judge_role_assignment = models.ForeignKey("events.EventRoleAssignment", on_delete=models.PROTECT, related_name="+")
    submission_snapshot = models.ForeignKey("events.SubmissionSnapshot", on_delete=models.PROTECT, related_name="+")
    track = models.ForeignKey("events.HackathonTrack", null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    room = models.CharField(max_length=64, blank=True)
    batch = models.CharField(max_length=64, default="main")
    state = models.CharField(max_length=16, default="assigned", choices=[(v, v) for v in
                            ("assigned", "scored", "skipped", "recused", "invalidated")])
    assigned_at = models.DateTimeField(auto_now_add=True)
    reason = models.ForeignKey(JudgingReason, null=True, blank=True, on_delete=models.PROTECT, related_name="+")

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=("round", "judge_role_assignment", "submission_snapshot"), name="ev_judge_snapshot_once"),
            models.CheckConstraint(condition=models.Q(state__in=("assigned", "scored", "skipped", "recused", "invalidated")),
                                   name="ev_judge_assignment_state"),
        ]


class JudgingRoundProject(models.Model):
    round = models.ForeignKey("events.JudgingRound", on_delete=models.CASCADE, related_name="projects")
    snapshot = models.ForeignKey("events.SubmissionSnapshot", on_delete=models.PROTECT, related_name="+")

    class Meta:
        constraints = [models.UniqueConstraint(fields=("round", "snapshot"), name="ev_round_project")]


class JudgeScore(ScopedPiiModelMixin, PrivateRecord, EventOwned):
    assignment = models.OneToOneField(JudgeAssignment, on_delete=models.CASCADE, related_name="score")
    criterion_values = models.JSONField(default=dict)
    notes = models.TextField(blank=True, max_length=4000)
    # #180 S4: written FOR the team, separate from the private notes; shown only once the round releases it.
    team_feedback = models.TextField(blank=True, max_length=4000)
    submitted_at = models.DateTimeField(null=True, blank=True)
    saved_at = models.DateTimeField(null=True, blank=True)  # L21b: the progress view's stale-draft clock.


class JudgeRankingBallot(EventOwned):
    round = models.ForeignKey("events.JudgingRound", on_delete=models.CASCADE, related_name="ballots")
    judge = models.ForeignKey("events.EventRoleAssignment", on_delete=models.PROTECT, related_name="+")
    batch = models.CharField(max_length=64)
    submitted_at = models.DateTimeField()
    # Typed members below pin all exposed assignments, including unranked projects.
    class Meta:
        constraints = [models.UniqueConstraint(fields=("round", "judge", "batch"), name="ev_ballot_once")]


class JudgeRankingChoice(AppendOnly):
    ballot = models.ForeignKey(JudgeRankingBallot, on_delete=models.CASCADE, related_name="choices")
    assignment = models.ForeignKey(JudgeAssignment, on_delete=models.PROTECT, related_name="+")
    rank = models.PositiveSmallIntegerField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=("ballot", "assignment"), name="ev_ballot_assignment"),
            models.UniqueConstraint(fields=("ballot", "rank"), condition=models.Q(rank__isnull=False), name="ev_ballot_rank"),
            models.CheckConstraint(condition=models.Q(rank__isnull=True) | models.Q(rank__gte=1, rank__lte=3),
                                   name="ev_ballot_rank_range"),
        ]


class JudgeConflict(EventOwned):
    member = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="+")
    team = models.ForeignKey("events.HackathonTeam", on_delete=models.CASCADE, related_name="+")
    round = models.ForeignKey("events.JudgingRound", on_delete=models.CASCADE, related_name="conflicts")
    active = models.BooleanField(default=True)
    reason = models.ForeignKey(JudgingReason, on_delete=models.PROTECT, related_name="+")

    class Meta:
        constraints = [models.UniqueConstraint(fields=("round", "member", "team"), name="ev_judge_conflict")]

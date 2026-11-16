"""Pairwise (CrowdBT) judging rows. Results always come from a full replay of valid comparisons."""

from django.db import models
from django.db.models import F, Q

from apps.encryption.mappers import ScopedPiiModelMixin
from .models_base import AppendOnly, EventOwned, PrivateRecord

OUTCOMES = ("previous", "current", "skip")


class JudgePairwiseComparison(ScopedPiiModelMixin, PrivateRecord, EventOwned, AppendOnly):
    round = models.ForeignKey("events.JudgingRound", on_delete=models.PROTECT, related_name="pairwise_comparisons")
    judge = models.ForeignKey("events.EventRoleAssignment", on_delete=models.PROTECT, related_name="+")
    previous = models.ForeignKey("events.JudgeAssignment", on_delete=models.PROTECT, related_name="+")
    current = models.ForeignKey("events.JudgeAssignment", on_delete=models.PROTECT, related_name="+")
    outcome = models.CharField(max_length=8, choices=[(value, value) for value in OUTCOMES])
    notes = models.TextField(blank=True, max_length=2000)
    submitted_at = models.DateTimeField()
    sequence = models.PositiveIntegerField()

    class Meta:
        ordering = ("round", "sequence")
        constraints = [
            models.UniqueConstraint(fields=("round", "sequence"), name="ev_pairwise_sequence"),
            models.UniqueConstraint(fields=("round", "judge", "previous", "current"), name="ev_pairwise_pair_once"),
            models.CheckConstraint(condition=~Q(previous=F("current")), name="ev_pairwise_distinct"),
            models.CheckConstraint(condition=Q(outcome__in=OUTCOMES), name="ev_pairwise_outcome"),
        ]


class JudgePairwiseInvalidation(AppendOnly):
    comparison = models.OneToOneField(JudgePairwiseComparison, on_delete=models.PROTECT, related_name="invalidation")
    reason = models.ForeignKey("events.JudgingReason", on_delete=models.PROTECT, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)


class JudgePairwiseCursor(EventOwned):
    round = models.ForeignKey("events.JudgingRound", on_delete=models.CASCADE, related_name="pairwise_cursors")
    judge = models.ForeignKey("events.EventRoleAssignment", on_delete=models.PROTECT, related_name="+")
    previous = models.ForeignKey("events.JudgeAssignment", null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    current = models.ForeignKey("events.JudgeAssignment", null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    draw_count = models.PositiveIntegerField(default=0)  # seeded draws used so far (replayable picks)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=("round", "judge"), name="ev_pairwise_cursor_once")]

"""L21b finalists: an append-only advance from a finalized round into a draft round, and its one publication."""

from django.conf import settings
from django.db import models
from django.db.models import Q

from .models_base import AppendOnly


class FinalistAdvance(AppendOnly):
    """One applied selection. The newest advance into a target round is the current finalist list."""
    event = models.ForeignKey("events.Event", on_delete=models.CASCADE, related_name="+")
    source_round = models.ForeignKey("events.JudgingRound", on_delete=models.PROTECT, related_name="+")
    target_round = models.ForeignKey("events.JudgingRound", on_delete=models.PROTECT, related_name="+")
    selection = models.CharField(max_length=8, choices=(("top_n", "Top N"), ("manual", "Hand-picked")))
    top_n = models.PositiveSmallIntegerField(null=True, blank=True)
    fingerprint = models.CharField(max_length=64)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=Q(selection__in=("top_n", "manual")), name="ev_finalist_selection"),
            models.CheckConstraint(condition=~Q(source_round=models.F("target_round")), name="ev_finalist_distinct_rounds"),
            models.CheckConstraint(condition=Q(selection="manual") | Q(top_n__gte=1), name="ev_finalist_top_n"),
        ]


class JudgingFinalist(AppendOnly):
    advance = models.ForeignKey(FinalistAdvance, on_delete=models.CASCADE, related_name="finalists")
    snapshot = models.ForeignKey("events.SubmissionSnapshot", on_delete=models.PROTECT, related_name="+")
    source_rank = models.PositiveSmallIntegerField(null=True, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=("advance", "snapshot"), name="ev_finalist_once")]


class FinalistAnnouncement(AppendOnly):
    """Publishing finalists is separate from results and happens once per advance."""
    event = models.ForeignKey("events.Event", on_delete=models.CASCADE, related_name="+")
    advance = models.OneToOneField(FinalistAdvance, on_delete=models.PROTECT, related_name="announcement")
    published_at = models.DateTimeField()
    published_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")

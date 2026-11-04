"""Event-owned tracks, prizes and frozen-when-open judging configuration."""

from django.db import models
from django.db.models import F, Q

from .models_base import EventOwned


class HackathonTrack(EventOwned):
    name = models.CharField(max_length=160)
    description = models.TextField(blank=True, max_length=4000)
    website_section = models.ForeignKey("events.EventPageSection", null=True, blank=True,
                                      on_delete=models.SET_NULL, related_name="+")
    criteria = models.JSONField(default=dict)
    form = models.JSONField(default=dict)
    capacity = models.PositiveIntegerField(default=0)
    eligibility_rules = models.JSONField(default=dict)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ("order", "id")
        constraints = [models.UniqueConstraint(fields=("event", "name"), name="ev_track_name")]


class HackathonPrize(EventOwned):
    name = models.CharField(max_length=160)
    description = models.TextField(blank=True, max_length=4000)
    website_section = models.ForeignKey("events.EventPageSection", null=True, blank=True,
                                      on_delete=models.SET_NULL, related_name="+")
    track = models.ForeignKey(HackathonTrack, null=True, blank=True, on_delete=models.PROTECT, related_name="prizes")
    sponsor = models.ForeignKey("events.EventSponsor", null=True, blank=True,
                               on_delete=models.PROTECT, related_name="+")
    criteria = models.JSONField(default=dict)
    form = models.JSONField(default=dict)
    eligibility_rules = models.JSONField(default=dict)
    order = models.PositiveIntegerField(default=0)
    award_count = models.PositiveSmallIntegerField(default=1)
    winner_selection_mode = models.CharField(max_length=20, default="manager",
                                           choices=(("manager", "Manager"), ("sponsor_proposal", "Sponsor proposal")))
    # L21b (C-38): prize money per winner. Paid out only by hand, through the append-only payout ledger.
    amount_per_winner = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)

    class Meta:
        ordering = ("order", "id")
        constraints = [models.CheckConstraint(condition=Q(award_count__gte=1), name="ev_prize_awards_positive"),
                       models.CheckConstraint(condition=Q(amount_per_winner__isnull=True) | Q(amount_per_winner__gt=0),
                                              name="ev_prize_amount_positive")]


class JudgingRound(EventOwned):
    key = models.SlugField(max_length=64)
    mode = models.CharField(max_length=16, choices=(("weighted_1_5", "Weighted 1–5"), ("top3", "Top three"),
                                                    ("pairwise", "Pairwise comparison")))
    state = models.CharField(max_length=16, default="draft",
                            choices=[(v, v) for v in ("draft", "open", "closed", "finalized")])
    min_reviews = models.PositiveSmallIntegerField(default=3)
    criteria_revision = models.PositiveIntegerField(default=1)
    normalization = models.CharField(max_length=8, default="none", choices=(("none", "None"), ("zscore", "Z-score")))
    minutes_per_view = models.PositiveSmallIntegerField(default=4)
    judging_minutes = models.PositiveSmallIntegerField(default=45)
    opens_at = models.DateTimeField(null=True, blank=True)
    closes_at = models.DateTimeField(null=True, blank=True)
    configuration = models.JSONField(default=dict, editable=False)
    algorithm_version = models.CharField(max_length=40, default="spaceworks-judging-v1", editable=False)
    coverage_exception = models.ForeignKey("events.JudgingReason", null=True, blank=True,
                                         on_delete=models.PROTECT, related_name="+")
    # L21b per-round settings: who may pull unassigned projects, and never the same team twice.
    visibility = models.CharField(max_length=12, default="assigned",
                                  choices=(("assigned", "Assigned only"), ("all", "All judges see all")))
    fresh_eyes = models.BooleanField(default=False)
    advanced_from = models.ForeignKey("self", null=True, blank=True, on_delete=models.PROTECT, related_name="+")

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=("event", "key"), name="ev_round_key"),
            models.CheckConstraint(condition=Q(min_reviews__gte=3), name="ev_round_three_reviews"),
            models.CheckConstraint(condition=Q(mode__in=("weighted_1_5", "top3", "pairwise")), name="ev_round_mode"),
            models.CheckConstraint(condition=Q(state__in=("draft", "open", "closed", "finalized")), name="ev_round_state"),
            models.CheckConstraint(condition=Q(normalization__in=("none", "zscore")), name="ev_round_normalization"),
            models.CheckConstraint(condition=Q(minutes_per_view__gte=1, judging_minutes__gte=1), name="ev_round_timing"),
            models.CheckConstraint(condition=Q(visibility__in=("assigned", "all")), name="ev_round_visibility"),
            models.CheckConstraint(condition=Q(opens_at__isnull=True) | Q(closes_at__isnull=True)
                                   | Q(closes_at__gt=F("opens_at")), name="ev_round_window"),
        ]


class JudgingPanelSeat(models.Model):
    """L21b: an optional round panel. With seats, only these judges are assigned or pull work."""
    round = models.ForeignKey(JudgingRound, on_delete=models.CASCADE, related_name="panel_seats")
    judge_role_assignment = models.ForeignKey("events.EventRoleAssignment", on_delete=models.PROTECT, related_name="+")

    class Meta:
        constraints = [models.UniqueConstraint(fields=("round", "judge_role_assignment"), name="ev_round_panel_seat")]


class JudgingCriterion(models.Model):
    round = models.ForeignKey(JudgingRound, on_delete=models.CASCADE, related_name="criteria")
    key = models.SlugField(max_length=64)
    label = models.CharField(max_length=160)
    weight = models.DecimalField(max_digits=10, decimal_places=4)
    anchors = models.JSONField()
    priority = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ("priority", "id")
        constraints = [
            models.UniqueConstraint(fields=("round", "key"), name="ev_criterion_key"),
            models.CheckConstraint(condition=Q(weight__gt=0), name="ev_criterion_weight"),
        ]

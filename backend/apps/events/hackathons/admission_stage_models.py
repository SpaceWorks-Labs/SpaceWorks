"""Multi-stage application review (#128 C-33): stages, panels, assignments, reviews, entries.

A stage is a review round on the way to a decision. Each has its own reviewer panel,
criteria (at most ten, scored 1 to 5), blind switch and target of 1 to 20 reviews per
application. Criteria, blind and target freeze with the first review. An application's
path through the stages is an append-only list of entries; the newest `entered` row is
the stage it stands in. Panel membership is the only authority a reviewer holds: it
opens that stage's review workspace and nothing else (never event staff authority).
"""
from django.conf import settings
from django.db import models
from django.db.models import F, Q

from apps.encryption.mappers import ScopedPiiModelMixin

MAX_STAGES = 20
MAX_CRITERIA = 10


class AdmissionStage(models.Model):
    class State(models.TextChoices):
        DRAFT = "draft", "Draft"
        OPEN = "open", "Open"
        CLOSED = "closed", "Closed"

    class Strategy(models.TextChoices):
        BALANCED = "balanced", "Balanced"
        RANDOM = "random", "Random"

    event = models.ForeignKey("events.Event", on_delete=models.CASCADE, related_name="admission_stages")
    position = models.PositiveSmallIntegerField()
    name = models.CharField(max_length=120)
    state = models.CharField(max_length=8, choices=State.choices, default=State.DRAFT)
    reviews_per_application = models.PositiveSmallIntegerField(default=1)
    blind = models.BooleanField(default=False)
    criteria = models.JSONField(default=list, blank=True)
    guidance = models.TextField(blank=True, default="", max_length=4000)
    opens_at = models.DateTimeField(null=True, blank=True)
    closes_at = models.DateTimeField(null=True, blank=True)
    assignment_strategy = models.CharField(max_length=8, choices=Strategy.choices, default=Strategy.BALANCED)
    assignment_seed = models.CharField(max_length=64, blank=True, default="")
    assignment_fingerprint = models.CharField(max_length=64, blank=True, default="")
    assigned_at = models.DateTimeField(null=True, blank=True)
    frozen_at = models.DateTimeField(null=True, blank=True)
    version = models.PositiveIntegerField(default=1)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                   related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["event_id", "position"]
        constraints = [
            models.UniqueConstraint(fields=["event", "position"], name="admission_stage_position_unique"),
            models.CheckConstraint(condition=Q(position__gte=1, position__lte=MAX_STAGES),
                                   name="admission_stage_position_bounds"),
            models.CheckConstraint(condition=Q(reviews_per_application__gte=1, reviews_per_application__lte=20),
                                   name="admission_stage_review_target_bounds"),
            models.CheckConstraint(condition=Q(opens_at__isnull=True) | Q(closes_at__isnull=True)
                                   | Q(closes_at__gt=F("opens_at")), name="admission_stage_window"),
        ]


class AdmissionStageReviewer(models.Model):
    stage = models.ForeignKey(AdmissionStage, on_delete=models.CASCADE, related_name="panel")
    reviewer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                                 related_name="admission_stage_panels")
    added_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                 related_name="+")
    added_at = models.DateTimeField(auto_now_add=True)
    removed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["stage", "reviewer"], condition=Q(removed_at__isnull=True),
                                               name="admission_stage_reviewer_live")]


class AdmissionStageAssignment(models.Model):
    class State(models.TextChoices):
        ASSIGNED = "assigned", "Assigned"
        SUBMITTED = "submitted", "Submitted"
        RECUSED = "recused", "Recused"

    stage = models.ForeignKey(AdmissionStage, on_delete=models.CASCADE, related_name="assignments")
    application = models.ForeignKey("events.HackathonApplication", on_delete=models.CASCADE,
                                    related_name="stage_assignments")
    reviewer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                                 related_name="admission_stage_assignments")
    state = models.CharField(max_length=10, choices=State.choices, default=State.ASSIGNED)
    plan_fingerprint = models.CharField(max_length=64)
    assigned_at = models.DateTimeField(auto_now_add=True)
    submitted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["stage", "application", "reviewer"],
                                               name="admission_stage_assignment_unique")]


class AdmissionStageReview(ScopedPiiModelMixin, models.Model):
    assignment = models.OneToOneField(AdmissionStageAssignment, on_delete=models.CASCADE, related_name="review")
    scores = models.JSONField(default=dict)
    notes = models.TextField(blank=True, default="")
    submitted_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValueError("Submitted stage reviews are immutable.")
        return super().save(*args, **kwargs)


class AdmissionStageEntry(models.Model):
    """Append-only: an application entering, advancing from or leaving a stage."""

    class Kind(models.TextChoices):
        ENTERED = "entered", "Entered"
        ADVANCED = "advanced", "Advanced"
        LEFT = "left", "Left"

    event = models.ForeignKey("events.Event", on_delete=models.CASCADE, related_name="+")
    application = models.ForeignKey("events.HackathonApplication", on_delete=models.CASCADE,
                                    related_name="stage_entries")
    stage = models.ForeignKey(AdmissionStage, on_delete=models.PROTECT, related_name="entries")
    kind = models.CharField(max_length=8, choices=Kind.choices)
    decision = models.ForeignKey("events.ApplicationDecision", null=True, blank=True, on_delete=models.SET_NULL,
                                 related_name="+")
    reason_code = models.CharField(max_length=40, blank=True, default="")
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                              related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["application_id", "pk"]
        indexes = [models.Index(fields=["application", "-id"], name="admission_stage_entry_latest")]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValueError("Stage entries are append-only.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError("Stage entries are append-only.")

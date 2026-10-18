"""Private decisions and review evidence, never participant projections."""
from django.conf import settings
from django.db import models
from django.db.models import Q
from apps.encryption.mappers import ScopedPiiModelMixin


def subject_check():
    return Q(application__isnull=False, cohort__isnull=True) | Q(application__isnull=True, cohort__isnull=False)


class ApplicationReviewAssignment(models.Model):
    event = models.ForeignKey("events.Event", on_delete=models.CASCADE)
    application = models.ForeignKey("events.HackathonApplication", on_delete=models.CASCADE, null=True, blank=True, related_name="review_assignments")
    cohort = models.ForeignKey("events.HackathonApplicationCohort", on_delete=models.CASCADE, null=True, blank=True, related_name="review_assignments")
    reviewer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="application_review_assignments")
    round = models.PositiveIntegerField(default=1)
    state = models.CharField(max_length=12, default="assigned", choices=[(v, v) for v in ("assigned", "submitted", "recused")])
    version = models.PositiveIntegerField(default=1)
    rubric_revision = models.PositiveIntegerField(default=1)
    assigned_at = models.DateTimeField(auto_now_add=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    recusal_code = models.CharField(max_length=40, blank=True)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=subject_check(), name="ha_review_one_subject"),
            models.UniqueConstraint(fields=["application", "reviewer", "round"], condition=Q(application__isnull=False), name="ha_review_application_unique"),
            models.UniqueConstraint(fields=["cohort", "reviewer", "round"], condition=Q(cohort__isnull=False), name="ha_review_cohort_unique"),
        ]


class ApplicationReview(ScopedPiiModelMixin, models.Model):
    assignment = models.OneToOneField(ApplicationReviewAssignment, on_delete=models.CASCADE, related_name="review")
    scores = models.JSONField(default=dict)
    notes = models.TextField(blank=True)
    submitted_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValueError("Submitted reviews are immutable; recuse or open a new round.")
        return super().save(*args, **kwargs)


class ApplicationReviewConflict(models.Model):
    event = models.ForeignKey("events.Event", on_delete=models.CASCADE)
    reviewer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    application = models.ForeignKey("events.HackathonApplication", on_delete=models.CASCADE, null=True, blank=True)
    cohort = models.ForeignKey("events.HackathonApplicationCohort", on_delete=models.CASCADE, null=True, blank=True)
    reason_code = models.CharField(max_length=40, default="declared")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.CheckConstraint(condition=subject_check(), name="ha_conflict_one_subject")]


class ApplicationDecisionBatch(models.Model):
    event = models.ForeignKey("events.Event", on_delete=models.CASCADE)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    state = models.CharField(max_length=12, default="draft", choices=[(v, v) for v in ("draft", "committed", "cancelled")])
    version = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    committed_at = models.DateTimeField(null=True, blank=True)


class ApplicationDecision(models.Model):
    batch = models.ForeignKey(ApplicationDecisionBatch, on_delete=models.CASCADE, related_name="decisions")
    application = models.ForeignKey("events.HackathonApplication", on_delete=models.PROTECT, null=True, blank=True, related_name="decisions")
    cohort = models.ForeignKey("events.HackathonApplicationCohort", on_delete=models.PROTECT, null=True, blank=True, related_name="decisions")
    outcome = models.CharField(max_length=8, choices=[(v, v) for v in ("offer", "waitlist", "reject")])
    reason_code = models.CharField(max_length=40)
    expected_subject_version = models.PositiveIntegerField()
    sent_revision = models.PositiveIntegerField(null=True, blank=True)
    active_draft = models.BooleanField(default=True)
    review_override_code = models.CharField(max_length=40, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=subject_check(), name="ha_decision_one_subject"),
            models.UniqueConstraint(fields=["application"], condition=Q(active_draft=True, application__isnull=False), name="ha_one_application_draft"),
            models.UniqueConstraint(fields=["cohort"], condition=Q(active_draft=True, cohort__isnull=False), name="ha_one_cohort_draft"),
        ]

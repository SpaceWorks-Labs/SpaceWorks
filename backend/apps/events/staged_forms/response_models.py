"""Mutable drafts point to immutable submitted answer revisions."""

from django.conf import settings
from django.db import models
from apps.encryption.mappers import ScopedPiiModelMixin


class StageFormAssignment(ScopedPiiModelMixin, models.Model):
    stage_form = models.ForeignKey("events.EventStageForm", on_delete=models.CASCADE, related_name="assignments")
    event = models.ForeignKey("events.Event", on_delete=models.CASCADE, related_name="stage_assignments")
    owner_member = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="stage_assignments")
    registration = models.ForeignKey("events.EventRegistration", on_delete=models.CASCADE, null=True, related_name="+")
    application = models.ForeignKey("events.HackathonApplication", on_delete=models.CASCADE, null=True, related_name="+")
    creation_operation_id = models.UUIDField(null=True)
    trigger_key = models.CharField(max_length=64)
    trigger_revision = models.PositiveBigIntegerField()
    due_revision = models.PositiveBigIntegerField(default=1)
    state = models.CharField(max_length=12, default="scheduled", choices=[(v, v) for v in (
        "scheduled", "open", "completed", "overdue", "cancelled")])
    version = models.PositiveBigIntegerField(default=1)
    pinned_form_revision = models.ForeignKey("events.EventFormRevision", on_delete=models.PROTECT, related_name="+")
    triggered_at = models.DateTimeField()
    opens_at = models.DateTimeField()
    base_due_at = models.DateTimeField()
    effective_due_at = models.DateTimeField()
    extension_reason = models.TextField(blank=True)
    extended_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+")
    extended_at = models.DateTimeField(null=True)
    next_stage_locked_at = models.DateTimeField(null=True)
    completed_response = models.ForeignKey("events.StageFormResponse", on_delete=models.SET_NULL, null=True, related_name="+")
    imported_paused = models.BooleanField(default=False)
    policy_snapshot = models.JSONField(default=dict)
    schedule_event_date_revision = models.PositiveBigIntegerField(default=1)
    cancelled_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+")
    cancelled_at = models.DateTimeField(null=True)
    cancellation_reason_code = models.CharField(max_length=64, blank=True)
    cancellation_reason = models.TextField(blank=True)
    reassigned_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+")
    reassigned_at = models.DateTimeField(null=True)
    reassignment_reason_code = models.CharField(max_length=64, blank=True)
    reassignment_reason = models.TextField(blank=True)

    class Meta:
        app_label = "events"
        indexes = [models.Index(fields=("state", "opens_at"), name="stage_assignment_open"),
                   models.Index(fields=("state", "effective_due_at"), name="stage_assignment_due")]
        constraints = [
            models.UniqueConstraint(fields=("stage_form", "owner_member"), name="stage_assignment_unique_owner"),
            models.CheckConstraint(condition=(models.Q(registration__isnull=False)
                | models.Q(application__isnull=False) | models.Q(creation_operation_id__isnull=False)),
                name="stage_assignment_subject"),
            models.CheckConstraint(condition=models.Q(effective_due_at__gt=models.F("opens_at")), name="stage_assignment_dates"),
            models.CheckConstraint(condition=models.Q(version__gte=1, due_revision__gte=1), name="stage_assignment_versions"),
        ]


class StageFormResponse(ScopedPiiModelMixin, models.Model):
    assignment = models.OneToOneField(StageFormAssignment, on_delete=models.CASCADE, related_name="response")
    event = models.ForeignKey("events.Event", on_delete=models.CASCADE, related_name="stage_responses")
    owner_member = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="stage_responses")
    state = models.CharField(max_length=12, default="draft", choices=[(v, v) for v in ("draft", "submitted", "locked", "withdrawn")])
    version = models.PositiveBigIntegerField(default=1)
    form_revision = models.ForeignKey("events.EventFormRevision", on_delete=models.PROTECT, related_name="+")
    answers_snapshot = models.TextField(default="{}")
    current_submitted_revision = models.ForeignKey("events.StageFormResponseRevision", on_delete=models.SET_NULL,
                                                  null=True, related_name="+")
    answer_event_date_revision = models.PositiveBigIntegerField(default=1)
    answer_locked_at = models.DateTimeField(null=True)
    submitted_at = models.DateTimeField(null=True)
    locked_at = models.DateTimeField(null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "events"
        constraints = [models.CheckConstraint(condition=models.Q(version__gte=1), name="stage_response_version_positive")]


class StageFormResponseRevision(ScopedPiiModelMixin, models.Model):
    response = models.ForeignKey(StageFormResponse, on_delete=models.CASCADE, related_name="submitted_revisions")
    revision = models.PositiveBigIntegerField()
    form_revision = models.ForeignKey("events.EventFormRevision", on_delete=models.PROTECT, related_name="+")
    answers_snapshot = models.TextField()
    submitted_at = models.DateTimeField()
    submitted_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+")
    date_revision = models.PositiveBigIntegerField()

    class Meta:
        app_label = "events"
        constraints = [
            models.UniqueConstraint(fields=("response", "revision"), name="stage_response_revision_unique"),
            models.CheckConstraint(condition=models.Q(revision__gte=1), name="stage_response_revision_positive"),
        ]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            from apps.payments.event_payouts.model_base import maintenance_fields
            allowed = maintenance_fields(self)
            requested = kwargs.get("update_fields")
            if requested is not None and not set(requested) <= allowed:
                raise RuntimeError("Maintenance may update mapped envelopes only.")
            kwargs["update_fields"] = allowed if requested is None else requested
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise RuntimeError("Submitted stage revisions require an authorized purge.")

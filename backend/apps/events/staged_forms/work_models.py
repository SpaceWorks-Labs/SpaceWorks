"""Bounded reconciliation/catch-up cursors; no answers or authority in work rows."""
from django.conf import settings
from django.db import models


class StageReconcileCursor(models.Model):
    event = models.OneToOneField("events.Event", on_delete=models.CASCADE, related_name="stage_reconcile_cursor")
    last_owner_id = models.PositiveBigIntegerField(default=0)
    version = models.PositiveBigIntegerField(default=1)

    class Meta:
        app_label = "events"


class StageActivationJob(models.Model):
    event = models.ForeignKey("events.Event", on_delete=models.CASCADE, related_name="stage_activation_jobs")
    stage_form = models.ForeignKey("events.EventStageForm", on_delete=models.CASCADE, related_name="activation_jobs")
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+")
    operation_id = models.UUIDField(unique=True)
    command_digest = models.CharField(max_length=64)
    participant_ids = models.JSONField()
    effective_due_at = models.DateTimeField()
    pinned_form_revision = models.ForeignKey("events.EventFormRevision", on_delete=models.PROTECT, related_name="+")
    state = models.CharField(max_length=12, default="pending", choices=[(v, v) for v in ("pending", "completed", "cancelled")])
    cursor = models.PositiveIntegerField(default=0)
    version = models.PositiveBigIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "events"

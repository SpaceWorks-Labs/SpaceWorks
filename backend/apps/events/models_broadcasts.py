"""Event campaign identity and concrete recipient uniqueness."""

from django.conf import settings
from django.db import models
from django.core.exceptions import ValidationError
from apps.integrations.broadcasts_models import BroadcastCampaign, BroadcastDelivery


class EventBroadcast(BroadcastCampaign):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        SCHEDULED = "scheduled", "Scheduled"
        QUEUED = "queued", "Queued"
        SENDING = "sending", "Sending"
        SENT = "sent", "Sent"
        CANCELLED = "cancelled", "Cancelled"
        FAILED = "failed", "Failed"

    status = models.CharField(max_length=10, choices=Status.choices, default=Status.DRAFT)
    event = models.ForeignKey("events.Event", on_delete=models.CASCADE, related_name="broadcasts")
    statuses = models.JSONField(default=list)
    attendance = models.CharField(max_length=12, default="any",
                                  choices=[("any", "Any"), ("attended", "Attended"), ("not_attended", "Not attended")])
    version = models.PositiveIntegerField(default=1)
    render_schema_version = models.PositiveSmallIntegerField(default=1, choices=[(1, "Legacy"), (2, "Composer")])
    design = models.CharField(max_length=12, default="classic",
                              choices=[(name, name.title()) for name in ("classic", "bold", "minimal")])
    available_at = models.DateTimeField(null=True, blank=True)
    confirmed_preview = models.ForeignKey("events.EventBroadcastPreview", null=True, blank=True,
                                         on_delete=models.RESTRICT, related_name="confirmed_campaigns")

    class Meta:
        indexes = [models.Index(fields=["status", "available_at"], name="event_broadcast_due_idx")]
        constraints = [
            models.CheckConstraint(condition=models.Q(render_schema_version__in=[1, 2]),
                                   name="event_broadcast_known_schema"),
            models.CheckConstraint(condition=(~models.Q(status="scheduled") | models.Q(
                render_schema_version=2, available_at__isnull=False, confirmed_preview__isnull=False)),
                name="event_broadcast_scheduled_proof"),
        ]


class EventBroadcastPreview(models.Model):
    """Immutable selection/count proof; contains no content or recipient list."""

    campaign = models.ForeignKey(EventBroadcast, on_delete=models.CASCADE, related_name="previews")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    content_sha256 = models.CharField(max_length=64)
    revision = models.CharField(max_length=64)
    recipient_count = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "events"

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError("Broadcast previews are immutable.")
        return super().save(*args, **kwargs)


class EventBroadcastDelivery(BroadcastDelivery):
    campaign = models.ForeignKey(EventBroadcast, on_delete=models.CASCADE, related_name="deliveries")

    class Meta:
        constraints = [models.UniqueConstraint(fields=["campaign", "recipient"], name="uniq_event_broadcast_account")]

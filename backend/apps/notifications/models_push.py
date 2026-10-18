"""Leased per-device children of canonical native-push deliveries."""

from django.db import models


class MemberPushDelivery(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        SENDING = "sending", "Sending"
        SENT = "sent", "Sent"
        FAILED = "failed", "Failed"
        SKIPPED = "skipped", "Skipped"
        HELD = "held", "Held"
        CANCELED = "canceled", "Canceled"

    envelope_delivery = models.ForeignKey(
        "integrations.NotificationDelivery", on_delete=models.CASCADE, related_name="push_children",
    )
    inbox_row = models.ForeignKey(
        "notifications.NotificationInboxRow", null=True, blank=True, on_delete=models.SET_NULL,
    )
    push_device = models.ForeignKey("integrations.PushDevice", on_delete=models.CASCADE)
    platform = models.CharField(max_length=16, blank=True)
    provider_source = models.CharField(max_length=8, blank=True)
    status = models.CharField(max_length=8, choices=Status.choices, default=Status.PENDING)
    lease_token = models.UUIDField(null=True, blank=True)
    lease_until = models.DateTimeField(null=True, blank=True)
    attempts = models.PositiveIntegerField(default=0)
    retryable = models.BooleanField(default=False)
    sent_at = models.DateTimeField(null=True, blank=True)
    last_error = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(
            fields=["envelope_delivery", "push_device"], name="uniq_envelope_push_device",
        )]
        indexes = [models.Index(fields=["status", "lease_until"], name="member_push_recovery_idx")]

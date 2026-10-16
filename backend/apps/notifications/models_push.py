"""Recoverable, per-device delivery telemetry for member inbox rows."""

from django.db import models


class MemberPushDelivery(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        SENDING = "sending", "Sending"
        SENT = "sent", "Sent"
        FAILED = "failed", "Failed"
        SKIPPED = "skipped", "Skipped"

    inbox_row = models.ForeignKey("notifications.NotificationInboxRow", on_delete=models.CASCADE)
    push_device = models.ForeignKey("integrations.PushDevice", on_delete=models.CASCADE)
    status = models.CharField(max_length=8, choices=Status.choices, default=Status.PENDING)
    lease_token = models.UUIDField(null=True, blank=True)
    lease_until = models.DateTimeField(null=True, blank=True)
    attempts = models.PositiveIntegerField(default=0)
    sent_at = models.DateTimeField(null=True, blank=True)
    last_error = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(
            fields=["inbox_row", "push_device"], name="uniq_member_push_delivery",
        )]
        indexes = [models.Index(fields=["status", "lease_until"], name="member_push_recovery_idx")]

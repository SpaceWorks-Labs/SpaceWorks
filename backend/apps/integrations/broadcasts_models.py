"""Abstract durable campaign records; concrete domain FKs stay in their own apps."""

from django.conf import settings
from django.db import models

from apps.encryption.mappers import ScopedPiiModelMixin


class BroadcastCampaign(ScopedPiiModelMixin, models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        QUEUED = "queued", "Queued"
        SENDING = "sending", "Sending"
        SENT = "sent", "Sent"
        CANCELLED = "cancelled", "Cancelled"
        FAILED = "failed", "Failed"

    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.CASCADE)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    subject = models.TextField()
    body = models.TextField()
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.DRAFT)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    queued_at = models.DateTimeField(null=True)
    completed_at = models.DateTimeField(null=True)
    # Pagination cursor, never a cached authorization proof.
    recipient_cursor = models.PositiveBigIntegerField(default=0)
    recipients_complete = models.BooleanField(default=False)

    class Meta:
        abstract = True


class BroadcastDelivery(models.Model):
    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    outbox = models.OneToOneField("integrations.EmailLog", null=True, on_delete=models.SET_NULL)
    status = models.CharField(max_length=8, default="pending",
                              choices=[(s, s.title()) for s in ("pending", "sent", "skipped", "failed")])
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True

"""Provider outcome ledgers; never store destinations, credentials or message content."""

from django.conf import settings
from django.db import models


class SmsSendLog(models.Model):
    makerspace = models.ForeignKey("makerspaces.Makerspace", null=True, blank=True, on_delete=models.CASCADE)
    purpose = models.CharField(max_length=32, default="authentication")
    provider_source = models.CharField(max_length=8, default="platform", choices=[("platform", "Platform"), ("own", "Own")])
    status = models.CharField(max_length=16, choices=[(s, s.title()) for s in ("sent", "failed", "skipped", "suppressed")])
    created_at = models.DateTimeField(auto_now_add=True)


class PushDeliveryAttempt(models.Model):
    """Staff sibling of MemberPushDelivery, using the same fenced lease protocol."""

    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.CASCADE, related_name="+")
    delivery_log = models.ForeignKey("integrations.NotificationDeliveryLog", on_delete=models.CASCADE)
    push_device = models.ForeignKey("integrations.PushDevice", on_delete=models.CASCADE)
    platform = models.CharField(max_length=16, blank=True)
    provider_source = models.CharField(max_length=8, default="platform")
    status = models.CharField(max_length=8, default="pending")
    lease_token = models.UUIDField(null=True, blank=True)
    lease_until = models.DateTimeField(null=True, blank=True)
    attempts = models.PositiveIntegerField(default=0)
    sent_at = models.DateTimeField(null=True, blank=True)
    last_error = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["delivery_log", "push_device"], name="unique_staff_push_attempt")]


class EmailProviderEvent(models.Model):
    """Replay identity is tenant-bound, even when a provider reuses an event ID."""

    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.CASCADE)
    event_id = models.CharField(max_length=200)
    reason = models.CharField(max_length=16, choices=[("bounce", "Bounce"), ("complaint", "Complaint")])
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["makerspace", "event_id"], name="unique_tenant_email_event")]

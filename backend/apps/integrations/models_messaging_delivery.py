"""Durable addressed delivery/outcome and normalized webhook inbox contracts."""
from django.utils.translation import gettext_lazy
from django.conf import settings
from django.db import models
from django.utils import timezone

from .models_messaging_consent import CHANNELS
from .notification_scope_contract import validate_notification_scope


class MessagingDelivery(models.Model):
    class SkipReason(models.TextChoices):
        TENANT_UNSERVABLE = "tenant_unservable", gettext_lazy("Tenant unavailable")
        MODULE_DISABLED = "module_disabled", gettext_lazy("Channel module disabled")
        FEATURE_UNAVAILABLE = "feature_unavailable", gettext_lazy("Source feature unavailable")
        MATRIX_DISABLED = "matrix_disabled", gettext_lazy("Notification rule disabled")
        ACCOUNT_INACTIVE = "account_inactive", gettext_lazy("Account inactive or restricted")
        NO_MEMBERSHIP = "no_membership", gettext_lazy("No active local membership")
        NO_TENANT_TIE = "no_tenant_tie", gettext_lazy("No tie to this makerspace")
        MEMBERSHIP_OPTED_OUT = "membership_opted_out", gettext_lazy("Membership notifications disabled")
        RECIPIENT_CHANGED = "recipient_changed", gettext_lazy("Recipient selection or scope changed")
        PERSONAL_DISABLED = "personal_disabled", gettext_lazy("Personal preference disabled")
        PHONE_UNVERIFIED = "phone_unverified", gettext_lazy("Phone unverified")
        NO_CONSENT = "no_consent", gettext_lazy("No live consent")
        SENDER_UNAVAILABLE = "sender_unavailable", gettext_lazy("Sender unavailable")
        NO_TEMPLATE = "no_template", gettext_lazy("No approved audience template")
        QUOTA_EXCEEDED = "quota_exceeded", gettext_lazy("Quota exhausted")
        SOURCE_CHANGED = "source_changed", gettext_lazy("Source removed or scope changed")
        IDENTITY_UNCONFIRMED = "identity_unconfirmed", gettext_lazy("Recipient correlation unconfirmed")

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        SENDING = "sending", "Sending"
        ACCEPTED = "accepted", "Accepted"
        SENT = "sent", "Sent"
        DELIVERED = "delivered", "Delivered"
        READ = "read", "Read"
        FAILED = "failed", "Failed"
        SKIPPED = "skipped", "Skipped"
        SUPPRESSED = "suppressed", "Suppressed"

    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.CASCADE)
    channel = models.CharField(max_length=16, choices=CHANNELS)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    audience = models.CharField(max_length=16, choices=[("member", "Member"), ("staff", "Staff")])
    feature = models.CharField(max_length=32)
    event = models.CharField(max_length=64)
    event_key = models.CharField(max_length=255)
    context = models.JSONField(default=dict)
    scope = models.JSONField(default=dict, validators=[validate_notification_scope])
    source_type = models.CharField(max_length=64, blank=True)
    source_id = models.CharField(max_length=64, blank=True)
    sender_key = models.CharField(max_length=255, blank=True)
    provider = models.CharField(max_length=16, blank=True)
    provider_source = models.CharField(max_length=16, blank=True, choices=[("own", "Own"), ("platform", "Platform")])
    provider_message_id = models.CharField(max_length=255, blank=True)
    recipient_alias_hash = models.CharField(max_length=64, blank=True)
    # The phone addressed at submission, even if User changes phone before callback.
    recipient_phone_hash = models.CharField(max_length=64, blank=True)
    template_name = models.CharField(max_length=512, blank=True)
    segments = models.PositiveSmallIntegerField(default=0)
    estimated_segments = models.PositiveSmallIntegerField(default=0)
    billed_segments = models.PositiveSmallIntegerField(null=True, blank=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    progress_rank = models.PositiveSmallIntegerField(default=0)
    skip_reason = models.CharField(max_length=64, blank=True, choices=SkipReason.choices)
    error_code = models.CharField(max_length=64, blank=True)
    attempts = models.PositiveSmallIntegerField(default=0)
    max_attempts = models.PositiveSmallIntegerField(default=4)
    next_attempt_at = models.DateTimeField(default=timezone.now)
    lease_token = models.UUIDField(null=True, blank=True)
    lease_until = models.DateTimeField(null=True, blank=True)
    quota_reserved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    accepted_at = models.DateTimeField(null=True, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)
    failed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["makerspace", "event_key", "user", "channel"], name="messaging_delivery_dedupe"),
            models.UniqueConstraint(fields=["provider", "provider_message_id"], condition=~models.Q(provider_message_id=""), name="messaging_provider_message"),
            models.CheckConstraint(condition=models.Q(progress_rank__lte=4), name="messaging_progress_rank"),
        ]
        indexes = [models.Index(fields=["status", "next_attempt_at"], name="messaging_delivery_due"),
                   models.Index(fields=["makerspace", "channel", "created_at"], name="messaging_delivery_cohort")]


class MessagingWebhookEvent(models.Model):
    class State(models.TextChoices):
        PENDING = "pending", "Pending"
        PROCESSED = "processed", "Processed"
        ABANDONED = "abandoned", "Abandoned"

    makerspace = models.ForeignKey("makerspaces.Makerspace", null=True, blank=True, on_delete=models.CASCADE)
    channel = models.CharField(max_length=16, choices=CHANNELS)
    provider = models.CharField(max_length=16)
    sender_key = models.CharField(max_length=255)
    dedupe_id = models.CharField(max_length=512)
    kind = models.CharField(max_length=16, choices=[("status", "Status"), ("inbound", "Inbound")])
    payload = models.JSONField(default=dict)
    state = models.CharField(max_length=16, choices=State.choices, default=State.PENDING)
    received_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    attempts = models.PositiveIntegerField(default=0)
    next_attempt_at = models.DateTimeField(default=timezone.now)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["provider", "dedupe_id"], name="messaging_webhook_dedupe")]
        indexes = [models.Index(fields=["state", "next_attempt_at"], name="messaging_webhook_due")]

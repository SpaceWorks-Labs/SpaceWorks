"""Device Adapter API v1, part 4: webhook push and per-machine-type safety defaults (device-bound, never exported)."""
import uuid

from django.utils.translation import gettext_noop
from django.conf import settings
from django.db import models
from django.utils import timezone


class AdapterWebhook(models.Model):
    """Where the server pushes content-free wake-ups for one adapter (for adapters that prefer push over polling).

    The HMAC secret is NEVER stored: it is derived from the deployment secret, this row's id and ``secret_version``,
    shown once when created or rotated, and rotation bumps the version. A run of failures disables the endpoint.
    """

    device = models.OneToOneField("devices.Device", on_delete=models.CASCADE, primary_key=True,
                                  related_name="adapter_webhook")
    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.CASCADE, related_name="+")
    url = models.CharField(max_length=500)
    enabled = models.BooleanField(default=True)
    secret_version = models.PositiveIntegerField(default=1)
    include_data = models.BooleanField(default=False)  # content-free envelope unless staff opt in
    consecutive_failures = models.PositiveSmallIntegerField(default=0)
    disabled_at = models.DateTimeField(null=True, blank=True)
    disabled_reason = models.CharField(max_length=48, blank=True)
    last_success_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                   related_name="+")
    created_at = models.DateTimeField(default=timezone.now)


class AdapterWebhookDelivery(models.Model):
    """One push attempt series (delivery log). Holds the small typed envelope only, never a secret."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        DELIVERED = "delivered", "Delivered"
        DEAD = "dead", gettext_noop("Gave up")

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.CASCADE, related_name="+")
    device = models.ForeignKey("devices.Device", on_delete=models.CASCADE, related_name="adapter_webhook_deliveries")
    event_type = models.CharField(max_length=48)
    envelope = models.JSONField(default=dict)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDING)
    attempts = models.PositiveSmallIntegerField(default=0)
    next_attempt_at = models.DateTimeField(default=timezone.now)
    last_status_code = models.PositiveSmallIntegerField(null=True, blank=True)
    last_error = models.CharField(max_length=48, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    delivered_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [models.Index(fields=["status", "next_attempt_at"], name="adapter_push_due_idx")]


class AdapterTypeProfile(models.Model):
    """Safety defaults for every adapter binding on machines of one type; a binding's own config overrides them."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.CASCADE, related_name="+")
    machine_type = models.ForeignKey("machines.MachineType", on_delete=models.CASCADE, related_name="+")
    config = models.JSONField(default=dict, blank=True)
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                   related_name="+")
    updated_at = models.DateTimeField(default=timezone.now)

    class Meta:
        constraints = [models.UniqueConstraint(fields=("makerspace", "machine_type"),
                                               name="adapter_type_profile_once")]

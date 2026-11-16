"""Durable reconciliation checkpoints; neither history nor receipt grants send authority."""
import json

from django.db import models
from django.utils import timezone
from django.conf import settings

from apps.makerspaces.secrets import decrypt_value, encrypt_value


class NotificationCutover(models.Model):
    # There is one deployment-wide switch, deliberately closed on installation.
    route = models.CharField(max_length=16, default="receipt_only",
        choices=[("receipt_only", "Receipt only"), ("canonical", "Canonical")])
    sending_enabled = models.BooleanField(default=False)
    barrier_at = models.DateTimeField(null=True)
    receipt_watermark = models.BigIntegerField(default=0)
    replay_watermark = models.BigIntegerField(default=0)
    snapshot = models.JSONField(default=dict)
    copied_at = models.DateTimeField(null=True)
    reconciled_at = models.DateTimeField(null=True)
    activated_at = models.DateTimeField(null=True)

    class Meta:
        constraints = [models.CheckConstraint(condition=models.Q(pk=1), name="notification_cutover_singleton")]


class NotificationIngress(models.Model):
    signed_user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    configuration = models.ForeignKey("integrations.ChannelConfiguration", null=True, on_delete=models.SET_NULL)
    makerspace = models.ForeignKey("makerspaces.Makerspace", null=True, on_delete=models.SET_NULL)
    makerspace_reference = models.BigIntegerField(null=True)
    configuration_reference = models.BigIntegerField(null=True)
    channel = models.CharField(max_length=16)
    provider = models.CharField(max_length=32)
    transport = models.CharField(max_length=24)
    sender_key = models.CharField(max_length=255)
    generation = models.PositiveIntegerField(default=0)
    credential_version = models.PositiveIntegerField(default=0)
    integration_identity = models.CharField(max_length=255, blank=True)
    dedupe_key = models.CharField(max_length=64, unique=True)
    # Endpoint proofs contain private destinations/codes. Never retain raw JSON here.
    payload = models.TextField()
    protection_applied = models.BooleanField(default=False)
    state = models.CharField(max_length=16, default="pending",
        choices=[("pending", "Pending"), ("processed", "Processed"), ("held", "Held")])
    attempts = models.PositiveIntegerField(default=0)
    next_attempt_at = models.DateTimeField(default=timezone.now)
    last_error = models.CharField(max_length=64, blank=True)
    received_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True)

    class Meta:
        indexes = [models.Index(fields=["next_attempt_at", "id"], condition=~models.Q(state="processed"), name="notification_ingress_due")]

    def set_payload(self, value):
        self.payload = encrypt_value(json.dumps(value))

    def get_payload(self):
        return json.loads(decrypt_value(self.payload))


class NotificationLegacyMapping(models.Model):
    legacy_model = models.CharField(max_length=64)
    legacy_id = models.BigIntegerField()
    canonical_model = models.CharField(max_length=64)
    canonical_id = models.BigIntegerField()
    makerspace = models.ForeignKey("makerspaces.Makerspace", null=True, on_delete=models.SET_NULL)
    disposition = models.CharField(max_length=32)
    snapshot = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["legacy_model", "legacy_id"], name="notification_legacy_mapping")]


class NotificationCredentialVersion(models.Model):
    configuration = models.ForeignKey("integrations.ChannelConfiguration", null=True, on_delete=models.SET_NULL,
        related_name="credential_versions")
    configuration_reference = models.BigIntegerField()
    makerspace_reference = models.BigIntegerField()
    generation = models.PositiveIntegerField()
    provider = models.CharField(max_length=32)
    integration_identity = models.CharField(max_length=255)
    sender_key = models.CharField(max_length=255)
    credentials = models.TextField(blank=True)
    retired_at = models.DateTimeField(null=True)
    wiped_at = models.DateTimeField(null=True)

    def get_credentials(self):
        return json.loads(decrypt_value(self.credentials)) if self.credentials else {}

    class Meta:
        constraints = [models.UniqueConstraint(fields=["configuration_reference", "generation"], name="notification_credential_generation")]


class NotificationProviderReference(models.Model):
    """Physical sender correlation survives account/tenant deletion, without contacts."""
    provider = models.CharField(max_length=32)
    sender_key = models.CharField(max_length=255)
    provider_id = models.CharField(max_length=255)
    phone_hash = models.CharField(max_length=64, blank=True)
    delivery_reference = models.BigIntegerField(null=True)
    makerspace_reference = models.BigIntegerField(null=True)
    generation = models.PositiveIntegerField(default=0)
    attempt = models.PositiveSmallIntegerField(default=0)
    ambiguous = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["provider", "sender_key", "provider_id"], name="notification_provider_reference")]

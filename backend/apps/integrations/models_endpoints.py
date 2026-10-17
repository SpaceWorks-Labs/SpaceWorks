"""Proofs belong to a specific account, tenant and installed integration."""

from django.conf import settings
from django.db import models

from apps.encryption.mappers import ScopedPiiModelMixin
from .notification_enums import NotificationChannel

PERSONAL_CHAT_CHANNELS = ("telegram", "slack", "mattermost", "discord", "whatsapp")


class ChannelConfiguration(models.Model):
    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.CASCADE)
    channel = models.CharField(max_length=16, choices=NotificationChannel.choices)
    enabled = models.BooleanField(default=False)
    room_enabled = models.BooleanField(default=False)
    personal_enabled = models.BooleanField(default=False)
    email_fallback = models.BooleanField(default=True)
    provider = models.CharField(max_length=32)
    integration_identity = models.CharField(max_length=255, blank=True)
    generation = models.PositiveIntegerField(default=1)
    credentials = models.TextField(blank=True)
    quotas = models.JSONField(default=dict)
    usage = models.JSONField(default=dict)
    updated_at = models.DateTimeField(auto_now=True)

    def set_credentials(self, value):
        import json
        from apps.makerspaces.secrets import encrypt_value
        self.credentials = encrypt_value(json.dumps(value)) if value else ""

    def get_credentials(self):
        import json
        from apps.makerspaces.secrets import decrypt_value
        return json.loads(decrypt_value(self.credentials)) if self.credentials else {}

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["makerspace", "channel"], name="uniq_channel_configuration"),
            models.CheckConstraint(condition=~models.Q(channel="whatsapp") | models.Q(provider__in=["twilio", "meta"]), name="whatsapp_provider_valid"),
        ]


class NotificationEndpoint(ScopedPiiModelMixin, models.Model):
    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    channel = models.CharField(max_length=16, choices=[(c, c) for c in PERSONAL_CHAT_CHANNELS])
    provider = models.CharField(max_length=32)
    destination = models.TextField()
    provider_subject = models.TextField()
    identity_digest = models.CharField(max_length=64)
    configuration = models.ForeignKey(ChannelConfiguration, on_delete=models.CASCADE)
    integration_identity = models.CharField(max_length=255)
    integration_generation = models.PositiveIntegerField()
    verification_state = models.CharField(max_length=16, default="verified", choices=[("verified", "Verified"), ("revoked", "Revoked")])
    verified_at = models.DateTimeField()
    consented_at = models.DateTimeField()
    consent_version = models.CharField(max_length=32)
    revoked_at = models.DateTimeField(null=True)
    last_inbound_at = models.DateTimeField(null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["makerspace", "user", "channel"], condition=models.Q(revoked_at__isnull=True), name="uniq_live_personal_endpoint"),
            models.UniqueConstraint(fields=["configuration", "identity_digest", "user"], condition=models.Q(revoked_at__isnull=True), name="uniq_live_provider_identity"),
        ]


class NotificationEndpointChallenge(ScopedPiiModelMixin, models.Model):
    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    configuration = models.ForeignKey(ChannelConfiguration, on_delete=models.CASCADE)
    integration_generation = models.PositiveIntegerField()
    integration_identity = models.CharField(max_length=255)
    endpoint = models.ForeignKey(NotificationEndpoint, null=True, on_delete=models.SET_NULL)
    code_digest = models.CharField(max_length=64, unique=True)
    expires_at = models.DateTimeField()
    consumed_at = models.DateTimeField(null=True)
    attempts = models.PositiveSmallIntegerField(default=0)
    consented_at = models.DateTimeField()
    consent_version = models.CharField(max_length=32)
    candidate_destination = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class WhatsAppTemplate(models.Model):
    configuration = models.ForeignKey(ChannelConfiguration, on_delete=models.CASCADE, related_name="templates")
    event = models.CharField(max_length=64)
    audience = models.CharField(max_length=16)
    locale = models.CharField(max_length=16, default="en")
    template_name = models.CharField(max_length=255)
    variables = models.JSONField(default=list)
    approved = models.BooleanField(default=False)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["configuration", "event", "audience", "locale"], name="uniq_whatsapp_template_binding")]

"""Immutable consent evidence and sender-scoped recipient protections."""
from django.utils.translation import gettext, gettext_noop
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from apps.encryption.mappers import ScopedPiiModelMixin

CHANNELS = [("sms", "SMS"), ("whatsapp", "WhatsApp")]


class MessagingConsent(ScopedPiiModelMixin, models.Model):
    class Action(models.TextChoices):
        OPTED_IN = "opted_in", gettext_noop("Opted in")
        OPTED_OUT = "opted_out", gettext_noop("Opted out")

    class Source(models.TextChoices):
        MEMBER_SETTINGS = "member_settings", gettext_noop("Member settings")
        NATIVE_APP = "native_app", gettext_noop("Native app")
        INBOUND_STOP = "inbound_stop", gettext_noop("Inbound STOP")
        ACCOUNT_ARCHIVE = "account_archive", gettext_noop("Account archive")

    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    channel = models.CharField(max_length=16, choices=CHANNELS)
    action = models.CharField(max_length=16, choices=Action.choices)
    phone_e164 = models.TextField(blank=True)
    phone_verified_at = models.DateTimeField(null=True, blank=True)
    source = models.CharField(max_length=24, choices=Source.choices)
    sender_key = models.CharField(max_length=255, blank=True)
    configuration_generation = models.PositiveIntegerField(default=0)
    endpoint = models.ForeignKey("integrations.NotificationEndpoint", null=True, on_delete=models.PROTECT)
    # An ordered JSON list records every lifted phone and alias suppression, W1.
    lifted_suppression_id = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["makerspace", "user", "channel", "-id"], name="messaging_consent_latest")]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            from .messaging.pii_maintenance import consent_phone_maintenance_allowed
            if set(kwargs.get("update_fields") or ()) != {"phone_e164"} or not consent_phone_maintenance_allowed(self.makerspace_id):
                raise ValidationError(gettext("Messaging consent is append-only."))
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError(gettext("Messaging consent is append-only."))


class MessagingSuppression(models.Model):
    class Reason(models.TextChoices):
        INBOUND_STOP = "inbound_stop", gettext_noop("Inbound STOP")
        PROVIDER_OPT_OUT = "provider_opt_out", gettext_noop("Provider opt-out")
        PERMANENT_FAILURE = "permanent_failure", gettext_noop("Permanent failure")

    channel = models.CharField(max_length=16, choices=CHANNELS)
    sender_key = models.CharField(max_length=255)
    recipient_hash = models.CharField(max_length=64)
    recipient_kind = models.CharField(max_length=8, choices=[("phone", "Phone"), ("alias", "Provider alias"),
        ("sender", "Unresolved sender protection")], default="phone")
    reason = models.CharField(max_length=24, choices=Reason.choices)
    created_at = models.DateTimeField(auto_now_add=True)
    provider_at = models.DateTimeField(null=True, blank=True)
    lifted_at = models.DateTimeField(null=True, blank=True)
    lifted_provider_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["channel", "sender_key", "recipient_hash"],
                      condition=models.Q(lifted_at__isnull=True), name="messaging_active_suppression")]


class MessagingRecipientAlias(models.Model):
    channel = models.CharField(max_length=16, choices=CHANNELS, default="whatsapp")
    sender_key = models.CharField(max_length=255)
    alias_hash = models.CharField(max_length=64)
    phone_hash = models.CharField(max_length=64)
    first_seen_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["channel", "sender_key", "alias_hash"], name="messaging_recipient_alias")]
        indexes = [models.Index(fields=["channel", "sender_key", "phone_hash"], name="messaging_alias_phone")]


class MessagingRecipientCorrelation(models.Model):
    class State(models.TextChoices):
        PROBING = "probing", "Probing"
        CONFIRMED = "confirmed", "Confirmed"
        BLOCKED = "blocked", "Blocked"

    channel = models.CharField(max_length=16, choices=[("whatsapp", "WhatsApp")], default="whatsapp")
    sender_key = models.CharField(max_length=255)
    phone_hash = models.CharField(max_length=64)
    state = models.CharField(max_length=16, choices=State.choices, default=State.PROBING)
    alias_known = models.BooleanField(default=False)
    probe_delivery = models.ForeignKey("integrations.MessagingDelivery", null=True, blank=True, on_delete=models.SET_NULL)
    probe_notification_delivery = models.ForeignKey("integrations.NotificationDelivery", null=True,
        blank=True, on_delete=models.SET_NULL)
    probe_started_at = models.DateTimeField(null=True, blank=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["channel", "sender_key", "phone_hash"], name="messaging_recipient_correlation")]

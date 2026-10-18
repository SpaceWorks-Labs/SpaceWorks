"""Addressed senders. Secrets use deployment encryption, never scoped PII."""
import secrets

from django.db import models

from apps.makerspaces.secrets import decrypt_value, encrypt_value


def verify_token():
    return secrets.token_urlsafe(32)


class MessagingSecrets(models.Model):
    class Meta:
        abstract = True

    def set_secret(self, field, raw):
        setattr(self, field, encrypt_value(raw) if raw else "")

    def get_secret(self, field):
        value = getattr(self, field)
        return decrypt_value(value) if value else ""


class PlatformWhatsAppSettings(MessagingSecrets, models.Model):
    is_enabled = models.BooleanField(default=False)
    app_id = models.CharField(max_length=64, blank=True)
    phone_number_id = models.CharField(max_length=64, blank=True)
    business_account_id = models.CharField(max_length=64, blank=True)
    access_token = models.TextField(blank=True)
    app_secret = models.TextField(blank=True)
    webhook_verify_token = models.CharField(max_length=128, default=verify_token)
    updated_at = models.DateTimeField(auto_now=True)

    @classmethod
    def load(cls):
        return cls.objects.get_or_create(pk=1)[0]

    def __str__(self):
        return "Platform WhatsApp settings"


class MakerspaceMessagingSettings(MessagingSecrets, models.Model):
    makerspace = models.OneToOneField("makerspaces.Makerspace", on_delete=models.CASCADE)
    use_platform_sender = models.BooleanField(default=True)
    sms_account_sid = models.CharField(max_length=64, blank=True)
    sms_auth_token = models.TextField(blank=True)
    sms_from_number = models.CharField(max_length=32, blank=True)
    sms_sender_key = models.CharField(max_length=255, null=True, blank=True, unique=True)
    whatsapp_phone_number_id = models.CharField(max_length=64, blank=True)
    whatsapp_business_account_id = models.CharField(max_length=64, blank=True)
    whatsapp_access_token = models.TextField(blank=True)
    whatsapp_app_secret = models.TextField(blank=True)
    whatsapp_webhook_verify_token = models.CharField(max_length=128, default=verify_token)
    whatsapp_sender_key = models.CharField(max_length=255, null=True, blank=True, unique=True)
    updated_at = models.DateTimeField(auto_now=True)


class MessagingSenderIdentity(models.Model):
    class Owner(models.TextChoices):
        PLATFORM_OTP = "platform_otp", "Platform OTP"
        PLATFORM = "platform", "Platform notifications"
        MAKERSPACE = "makerspace", "Makerspace"

    sender_key = models.CharField(max_length=255, unique=True)
    channel = models.CharField(max_length=16, choices=[("sms", "SMS"), ("whatsapp", "WhatsApp")])
    owner = models.CharField(max_length=16, choices=Owner.choices)
    makerspace = models.ForeignKey("makerspaces.Makerspace", null=True, blank=True, on_delete=models.SET_NULL)
    tenant_reference = models.BigIntegerField(null=True)
    active = models.BooleanField(default=True)
    retired_at = models.DateTimeField(null=True, blank=True)


class MessagingSenderCredential(MessagingSecrets, models.Model):
    identity = models.ForeignKey(MessagingSenderIdentity, on_delete=models.CASCADE, related_name="credentials")
    version = models.PositiveIntegerField()
    webhook_secret = models.TextField(blank=True)
    verify_token = models.CharField(max_length=128, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    retired_at = models.DateTimeField(null=True, blank=True)
    wiped_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["identity", "version"], name="messaging_credential_version")]


class WhatsAppTemplateBinding(models.Model):
    makerspace = models.ForeignKey("makerspaces.Makerspace", null=True, blank=True, on_delete=models.CASCADE)
    feature = models.CharField(max_length=32)
    event = models.CharField(max_length=64)
    audience = models.CharField(max_length=16, choices=[("member", "Member"), ("staff", "Staff")])
    business_account_id = models.CharField(max_length=64)
    template_name = models.CharField(max_length=512)
    language = models.CharField(max_length=16)
    parameters = models.JSONField(default=list, blank=True)
    is_active = models.BooleanField(default=True)
    needs_review = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["makerspace", "feature", "event", "audience"],
                                    condition=models.Q(makerspace__isnull=False), name="messaging_tenant_template"),
            models.UniqueConstraint(fields=["feature", "event", "audience"],
                                    condition=models.Q(makerspace__isnull=True), name="messaging_platform_template"),
        ]

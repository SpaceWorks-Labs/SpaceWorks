"""Fields/validation for I's existing platform and tenant settings serializers."""

from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from .mail_providers.config import PROVIDERS, validate_config
from .smtp_validation import validate_smtp_settings


def validate_provider_update(attrs, instance, *, tenant=False):
    provider = attrs.get("email_provider", getattr(instance, "email_provider", ""))
    try:
        if provider in {"", "inherit"}:
            if "email_provider_config" in attrs and attrs["email_provider_config"]:
                raise DjangoValidationError("Choose a provider before setting credentials.")
            if provider == "inherit" and not tenant:
                raise DjangoValidationError("Platform email cannot inherit tenant settings.")
            # Old SMTP writes keep their SSRF/TLS validation.
            if provider == "":
                validate_smtp_settings(attrs, instance)
            return attrs
        sender_field = "smtp_from_email" if tenant else "from_email"
        sender = attrs.get(sender_field, getattr(instance, sender_field, ""))
        values = attrs.get("email_provider_config")
        if values is None:
            values = (instance.get_email_provider_config()
                      if provider == getattr(instance, "email_provider", "") else {})
        validate_config(provider, values, sender)
        if tenant and provider == "ses" and values.get("workload_identity"):
            raise DjangoValidationError("Tenant SES requires dedicated credentials.")
        if provider == "smtp":
            validate_smtp_settings(attrs, instance)
            if not attrs.get("smtp_host", instance.smtp_host):
                raise DjangoValidationError("SMTP hostname is required.")
    except DjangoValidationError as exc:
        # Static validation messages only; ciphertext/provider exceptions never escape.
        if hasattr(exc, "error_dict"):
            # Field-keyed SMTP errors (smtp_host/smtp_port/smtp_use_tls) keep their field.
            raise serializers.ValidationError(exc.message_dict) from None
        raise serializers.ValidationError({"email_provider_config": exc.messages}) from None
    except Exception:
        raise serializers.ValidationError({"email_provider_config": "Email credentials are unavailable."}) from None
    return attrs


def apply_provider_update(instance, attrs):
    """Consume encrypted input only; caller handles remaining fields/passwords.

    Call before the existing ModelSerializer.update(), inside its audited service.
    """
    values = attrs.pop("email_provider_config", None)
    provider = attrs.get("email_provider", getattr(instance, "email_provider", ""))
    if values is not None:
        instance.set_email_provider_config(values)
    elif "email_provider" in attrs and provider != getattr(instance, "email_provider", ""):
        instance.set_email_provider_config({})
    if "email_provider" in attrs:
        instance.email_provider = provider
    return instance


class EmailProviderFields(serializers.Serializer):
    email_provider = serializers.ChoiceField(choices=["", "inherit", *PROVIDERS], required=False)
    email_provider_config = serializers.DictField(write_only=True, required=False)
    email_provider_configured = serializers.SerializerMethodField()

    def get_email_provider_configured(self, instance):
        try:
            provider = getattr(instance, "email_provider", "")
            if provider in {"", "inherit"}:
                return False
            from .mail_providers.selection import stored_config
            return stored_config(instance, tenant=hasattr(instance, "smtp_from_email")) is not None
        except Exception:
            return False

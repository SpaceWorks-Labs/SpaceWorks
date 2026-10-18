"""Platform DB > platform secret mount/env; tenants may explicitly inherit."""

import json
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured, ValidationError

from .config import validate_config


def stored_config(instance, *, tenant=False):
    provider = getattr(instance, "email_provider", "")
    host = (instance.smtp_host or "").strip()
    if provider in {"", "inherit"}:
        if not provider and host:  # Legacy rows before the data migration.
            provider = "smtp"
        else:
            return None
    sender = instance.smtp_from_email if tenant else instance.from_email
    sender = sender or settings.DEFAULT_FROM_EMAIL
    values = instance.get_email_provider_config() if provider != "smtp" else {}
    if tenant and provider == "ses" and values.get("workload_identity"):
        raise ValidationError("Tenant SES requires dedicated credentials.")
    return validate_config(provider, values, sender)


def environment_config():
    provider = getattr(settings, "EMAIL_PROVIDER", "")
    if not provider:
        return None  # Preserve the legacy Django EMAIL_BACKEND environment contract.
    legacy_backend = getattr(settings, "EMAIL_BACKEND", "")
    # SMTP/console/locmem are existing deployment defaults, not an HTTP selector.
    if legacy_backend.startswith("anymail.backends."):
        backend_provider = {"anymail.backends.amazon_ses.EmailBackend": "ses",
                            **{f"anymail.backends.{p}.EmailBackend": p for p in
                               ("resend", "postmark", "brevo", "mailgun", "sendgrid")}}.get(legacy_backend)
        if backend_provider != provider:
            raise ImproperlyConfigured("Email provider and backend do not match.")
    values = {}
    secret_path = getattr(settings, "EMAIL_PROVIDER_CONFIG_FILE", "")
    if secret_path:
        try:
            # Bound parsing/allocation even when an operator mounts the wrong file.
            with Path(secret_path).open("rb") as handle:
                raw = handle.read(16385)
            if len(raw) > 16384:
                raise ValueError()
            values = json.loads(raw)
        except (OSError, ValueError, TypeError):
            raise ImproperlyConfigured("Email provider secret mount is invalid.") from None
    return validate_config(provider, values, settings.DEFAULT_FROM_EMAIL)

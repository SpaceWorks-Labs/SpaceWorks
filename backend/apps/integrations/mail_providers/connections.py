"""Create isolated connections; only the selected provider receives credentials."""

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.mail import get_connection

from apps.integrations.smtp_validation import smtp_timeout_seconds, validate_smtp_endpoint
from .config import BACKENDS


def connection_for(config, instance=None, *, timeout=None):
    seconds = smtp_timeout_seconds() if timeout is None else timeout
    if not 0 < seconds <= 30:
        raise ValueError("Invalid email timeout.")
    provider, values = config.provider, config.credentials
    kwargs = {"fail_silently": False, "timeout": seconds}
    if provider != "smtp":
        kwargs.update(debug_api_requests=False)
    if provider == "smtp":
        if instance is None:
            kwargs.update(host=settings.EMAIL_HOST, port=settings.EMAIL_PORT,
                          username=settings.EMAIL_HOST_USER, password=settings.EMAIL_HOST_PASSWORD,
                          use_tls=settings.EMAIL_USE_TLS, use_ssl=settings.EMAIL_USE_SSL)
        else:
            kwargs.update(host=instance.smtp_host, port=instance.smtp_port,
                          username=instance.smtp_username or None,
                          password=instance.get_smtp_password() or None,
                          use_ssl=instance.smtp_use_ssl,
                          use_tls=instance.smtp_use_tls and not instance.smtp_use_ssl)
        if not (kwargs["host"] or "").strip():
            raise ValidationError("SMTP hostname is required.")
        validate_smtp_endpoint(kwargs["host"], kwargs["port"])
    elif provider == "ses":
        kwargs["mail_config"] = config
    elif provider == "postmark":
        kwargs["server_token"] = values["server_token"]
    else:
        kwargs["api_key"] = values["api_key"]
        if provider == "mailgun":
            kwargs.update(sender_domain=values["domain"], api_url=(
                "https://api.eu.mailgun.net/v3" if values["region"] == "eu"
                else "https://api.mailgun.net/v3"))
        elif provider in {"resend", "brevo"}:
            # Never inherit a global ANYMAIL_*_API_URL (including from another tenant).
            kwargs["api_url"] = {"resend": "https://api.resend.com/",
                                 "brevo": "https://api.brevo.com/v3/"}[provider]
    if provider == "postmark":
        kwargs["api_url"] = "https://api.postmarkapp.com/"
    connection = get_connection(BACKENDS[provider], **kwargs)
    connection.spaceworks_mail_config = config
    return connection, config.sender

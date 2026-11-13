import json
from unittest.mock import patch

import pytest
from django.core.exceptions import ImproperlyConfigured, ValidationError

from apps.integrations.mail_providers.config import validate_config
from apps.integrations.mail_providers.connections import connection_for
from apps.integrations.mail_providers.selection import environment_config
from apps.integrations.models_email import PlatformEmailSettings
from apps.integrations.email_provider_serializers import EmailProviderFields, validate_provider_update


@pytest.mark.parametrize("provider,credentials", [
    ("resend", {"api_key": "resend-secret"}), ("postmark", {"server_token": "postmark-secret"}),
    ("brevo", {"api_key": "brevo-secret"}), ("sendgrid", {"api_key": "sendgrid-secret"}),
    ("mailgun", {"api_key": "mailgun-secret", "domain": "mail.example.org", "region": "eu"}),
    ("ses", {"region": "ap-south-1", "access_key_id": "ses-access", "secret_access_key": "ses-secret"}),
])
def test_allowlist_passes_only_selected_provider_kwargs(provider, credentials):
    config = validate_config(provider, credentials, "Space Works <mail@example.org>")
    with patch("apps.integrations.mail_providers.connections.get_connection") as factory:
        connection_for(config)
    args = factory.call_args.kwargs
    assert not {"host", "port", "username", "password", "use_tls", "use_ssl"} & args.keys()
    assert args["fail_silently"] is False
    assert args["debug_api_requests"] is False
    assert "secret" not in repr(config)


@pytest.mark.parametrize("provider,credentials", [
    ("https://attacker.invalid", {}), ("resend", {"api_key": "x", "api_url": "http://localhost"}),
    ("postmark", {"api_key": "wrong-key"}), ("brevo", {"api_key": {"nested": "secret"}}),
    ("mailgun", {"api_key": "x", "domain": "https://bad", "region": "us"}),
    ("ses", {"region": "ap-south-1"}),
    ("ses", {"region": "ap-south-1", "workload_identity": True, "access_key_id": "x"}),
])
def test_untrusted_backend_urls_and_incomplete_credentials_are_rejected(provider, credentials):
    with pytest.raises(ValidationError):
        validate_config(provider, credentials, "mail@example.org")


def test_secret_mount_is_bounded_and_malformed_mount_never_falls_back(settings, tmp_path):
    settings.EMAIL_PROVIDER = "resend"
    settings.DEFAULT_FROM_EMAIL = "mail@example.org"
    secret = tmp_path / "mail.json"
    settings.EMAIL_PROVIDER_CONFIG_FILE = str(secret)
    secret.write_text(json.dumps({"api_key": "secret"}), encoding="utf-8")
    assert environment_config().provider == "resend"
    secret.write_text("x" * 16385, encoding="utf-8")
    with pytest.raises(ImproperlyConfigured, match="secret mount is invalid"):
        environment_config()


def test_platform_config_encrypts_and_serializer_never_echoes_credentials(settings):
    from cryptography.fernet import Fernet
    settings.API_CLIENT_ENC_KEY = Fernet.generate_key().decode()
    row = PlatformEmailSettings(email_provider="resend", from_email="mail@example.org")
    row.set_email_provider_config({"api_key": "private-key"})
    assert row.email_provider_config.startswith("fernet:")
    assert "private-key" not in row.email_provider_config
    assert row.get_email_provider_config() == {"api_key": "private-key"}
    response = EmailProviderFields(row).data
    assert response == {"email_provider": "resend", "email_provider_configured": True}


def test_http_provider_update_does_not_validate_stale_smtp_fields():
    row = PlatformEmailSettings(email_provider="resend", from_email="mail@example.org",
                                smtp_host="127.0.0.1")
    attrs = {"email_provider_config": {"api_key": "new-secret"}}
    assert validate_provider_update(attrs, row) == attrs


def test_smtp_update_rejects_mutually_exclusive_tls_flags():
    from apps.integrations.smtp_validation import validate_smtp_settings
    with pytest.raises(ValidationError, match="STARTTLS"):
        validate_smtp_settings({"smtp_use_tls": True, "smtp_use_ssl": True})


def test_tenant_cannot_borrow_platform_ses_workload_identity():
    from types import SimpleNamespace
    from rest_framework.exceptions import ValidationError as ApiValidationError
    row = SimpleNamespace(email_provider="ses", smtp_from_email="mail@example.org",
        get_email_provider_config=lambda: {"region": "ap-south-1", "workload_identity": True})
    with pytest.raises(ApiValidationError, match="dedicated credentials"):
        validate_provider_update({}, row, tenant=True)


def test_provider_and_explicit_legacy_http_backend_mismatch_refuses(settings):
    settings.EMAIL_PROVIDER = "resend"
    settings.EMAIL_BACKEND = "anymail.backends.mailgun.EmailBackend"
    with pytest.raises(ImproperlyConfigured, match="do not match"):
        environment_config()

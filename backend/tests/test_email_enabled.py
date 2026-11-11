import pytest
from types import SimpleNamespace
from rest_framework.test import APIClient

from apps.integrations.email import email_enabled


@pytest.fixture(autouse=True)
def legacy_email_selector(monkeypatch, settings):
    # These unit cases exercise legacy backend/SMTP eligibility; the DB provider
    # discriminator has its own provider-selection tests.
    settings.EMAIL_PROVIDER = ""
    monkeypatch.setattr("apps.integrations.models.PlatformEmailSettings.load",
                        lambda: SimpleNamespace(email_provider="", smtp_host=""))


def test_email_enabled_true_when_platform_configured_and_smtp_backend(monkeypatch, settings):
    # Platform SMTP only delivers when EMAIL_BACKEND is the SMTP backend (get_connection
    # uses it as the backend class); a configured platform host alone is not enough.
    settings.DEBUG = False
    settings.EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
    settings.EMAIL_HOST = ""
    monkeypatch.setattr("apps.integrations.email.platform_email_configured", lambda: True)

    assert email_enabled() is True


def test_email_enabled_false_when_platform_configured_but_console_backend(monkeypatch, settings):
    # Codex Stage-4 P2 regression: a platform SMTP host saved while EMAIL_BACKEND stays the
    # default console backend would only LOG mail — the gate must report disabled so the UI
    # never advertises a Forgot-Password path that silently never sends.
    settings.DEBUG = False
    settings.EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
    settings.EMAIL_HOST = ""
    monkeypatch.setattr("apps.integrations.email.platform_email_configured", lambda: True)

    assert email_enabled() is False


def test_email_enabled_true_for_smtp_backend_with_host(monkeypatch, settings):
    settings.DEBUG = False
    settings.EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
    settings.EMAIL_HOST = "smtp.example.com"
    monkeypatch.setattr("apps.integrations.email.platform_email_configured", lambda: False)

    assert email_enabled() is True


def test_email_enabled_false_for_console_backend_in_production_without_host(
    monkeypatch, settings
):
    settings.DEBUG = False
    settings.EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
    settings.EMAIL_HOST = ""
    monkeypatch.setattr("apps.integrations.email.platform_email_configured", lambda: False)

    assert email_enabled() is False


def test_email_enabled_false_for_console_backend_in_production_even_with_host(
    monkeypatch, settings
):
    settings.DEBUG = False
    settings.EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
    settings.EMAIL_HOST = "smtp.example.com"
    monkeypatch.setattr("apps.integrations.email.platform_email_configured", lambda: False)

    assert email_enabled() is False


def test_email_enabled_true_for_console_backend_in_debug(monkeypatch, settings):
    settings.DEBUG = True
    settings.EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
    settings.EMAIL_HOST = ""
    monkeypatch.setattr("apps.integrations.email.platform_email_configured", lambda: False)

    assert email_enabled() is True


@pytest.mark.django_db
def test_public_config_returns_email_enabled_without_api_client_hmac(
    monkeypatch, settings
):
    settings.API_CLIENT_AUTH_REQUIRED = True
    monkeypatch.setattr("apps.makerspaces.config_views.email_enabled", lambda: True)

    response = APIClient().get("/api/v1/config")

    assert response.status_code == 200
    # /config also carries the mobile `native` block since the mobile-backend merge;
    # this test covers only the two web keys.
    assert response.data["email_enabled"] is True
    assert response.data["public_image_max_bytes"] == settings.PUBLIC_IMAGE_MAX_BYTES

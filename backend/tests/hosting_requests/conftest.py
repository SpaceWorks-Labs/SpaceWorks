import pytest
from django.core.cache import cache


MANAGED_SUFFIX = ".space-works.test"
BASE_URL = "https://app.space-works.test"


@pytest.fixture
def managed(settings, monkeypatch):
    """A managed platform that can send platform mail and build public links."""
    settings.PLATFORM_DOMAIN_SUFFIX = MANAGED_SUFFIX
    settings.PUBLIC_APP_BASE_URL = BASE_URL
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    settings.INFRA_HOSTS = {"testserver", "localhost", "127.0.0.1"}
    monkeypatch.setattr("apps.hosting_requests.availability.email_enabled", lambda: True)
    cache.clear()
    yield settings
    cache.clear()


@pytest.fixture
def self_host(settings, monkeypatch):
    settings.PLATFORM_DOMAIN_SUFFIX = ""
    settings.PUBLIC_APP_BASE_URL = BASE_URL
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    monkeypatch.setattr("apps.hosting_requests.availability.email_enabled", lambda: True)
    cache.clear()
    yield settings
    cache.clear()

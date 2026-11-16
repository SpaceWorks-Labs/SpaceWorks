import pytest
from django.core.cache import cache


@pytest.fixture
def mailbox(settings):
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    from django.core import mail
    mail.outbox.clear()
    cache.clear()
    return mail.outbox


@pytest.fixture
def managed(settings, monkeypatch):
    settings.PLATFORM_DOMAIN_SUFFIX = ".space-works.test"
    settings.PUBLIC_APP_BASE_URL = "https://app.space-works.test"
    settings.INFRA_HOSTS = {"testserver", "localhost", "127.0.0.1"}
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    monkeypatch.setattr("apps.hosting_requests.availability.email_enabled", lambda: True)
    cache.clear()
    yield settings
    cache.clear()


@pytest.fixture
def plans_on(managed):
    managed.MANAGED_PLANS_ENABLED = True
    return managed

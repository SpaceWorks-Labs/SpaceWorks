"""Shared fixtures for the S-B login-security tests (local only)."""

from types import SimpleNamespace

import pytest
from django.core.cache import cache
from django.utils import timezone

from apps.accounts.models import User

ORIGIN = "http://localhost:5173"
PASSWORD = "risk-pass-123!"


@pytest.fixture
def mail(monkeypatch, settings):
    """Email "works": codes and alerts are captured instead of sent."""
    settings.AUTH_COOKIE_SECURE = False
    settings.PASSWORD_BREACH_CHECK_ENABLED = False
    settings.PUBLIC_APP_BASE_URL = "https://app.example.test"
    cache.clear()
    sent = []
    monkeypatch.setattr("apps.integrations.email.email_enabled", lambda: True)

    def dispatch(**kwargs):
        sent.append(kwargs)
        return SimpleNamespace(status="sent")

    monkeypatch.setattr("apps.integrations.dispatch.dispatch_email", dispatch)
    return sent


def person(username="risk-person", **fields):
    return User.objects.create_user(username=username, email=f"{username}@example.test", password=PASSWORD,
                                    email_verified_at=timezone.now(), **fields)


def login(client, user, **headers):
    return client.post("/api/v1/auth/login", {"username": user.username, "password": PASSWORD},
                       format="json", HTTP_ORIGIN=ORIGIN, **headers)


def code_from(sent):
    mails = [item for item in sent if item.get("event") == "security_login_code"]
    assert mails, "no login code was mailed"
    body = mails[-1]["text_body"]
    return next(token for token in body.split() if token.isdigit() and len(token) == 6)

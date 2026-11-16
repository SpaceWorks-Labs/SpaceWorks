"""Shared real account/session fixtures for the phase 1d contract tests."""

from datetime import timedelta
from uuid import uuid4

import pytest
from cryptography.fernet import Fernet
from django.utils import timezone

from apps.accounts import reauthentication
from apps.accounts.models import User
from apps.makerspaces.secrets import encrypt_value
from tests.accounts.test_reauthentication import ORIGIN, PASSWORD, request


@pytest.fixture(autouse=True)
def m1d_config(settings, monkeypatch):
    settings.API_CLIENT_ENC_KEY = Fernet.generate_key().decode()
    settings.CORS_ALLOWED_ORIGINS = [ORIGIN]
    settings.ACCOUNT_DELETION_RETENTION_DAYS = 90

    def unexpected_http(*args, **kwargs):
        raise AssertionError("Phase 1d provider HTTP must be mocked")

    monkeypatch.setattr("requests.sessions.Session.request", unexpected_http)


def account(*, password=PASSWORD, verified=True):
    name = "m1d-" + uuid4().hex
    return User.objects.create_user(
        username=name, password=password, email=name + "@example.test",
        email_verified_at=timezone.now() if verified else None,
    )


def proven(user):
    req = request(user, surface="member")
    reauthentication.verify(req, password=PASSWORD)
    return req


def due(user):
    """Model a committed Stage A archive without forging a recent-auth proof."""
    user.is_active = False
    user.set_unusable_password()
    user.deletion_requested_at = timezone.now() - timedelta(days=91)
    user.deletion_purge_after = timezone.now() - timedelta(days=1)
    user.deletion_email_ciphertext = encrypt_value(user.email)
    user.save()
    return user


def purge(user):
    from apps.accounts.account_purge import purge_account
    counts = {"purged": 0, "skipped": 0, "failed": 0}
    purge_account(user.pk, counts)
    user.refresh_from_db()
    return counts

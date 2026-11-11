"""Real archive and recovery proofs shared by Part C contract tests."""

from django.core.cache import cache
from django.utils import timezone
import pytest

from apps.accounts import account_deletion
from apps.accounts.models import PasswordResetEnvelope
from apps.accounts.services_password_reset import request_password_reset
from apps.accounts import services_password_reset_drain as drain
from tests.accounts.test_support_m1d import account, proven

PASSWORD = "Returned-Member-strong-773!"


@pytest.fixture(autouse=True)
def restore_config(monkeypatch):
    cache.clear()
    monkeypatch.setattr(drain, "email_enabled", lambda: True)
    monkeypatch.setattr("apps.accounts.views_password.email_enabled", lambda: True)
    monkeypatch.setattr("apps.accounts.apple_revocation._enqueue", lambda pk: None)


def archive(user=None):
    user = user or account()
    account_deletion.request_deletion(proven(user))
    user.refresh_from_db()
    return user


def email_proof(user):
    request_password_reset(user.email)
    claim = drain.claim_pending_envelopes()[0]
    attempt = drain.prepare_delivery(claim)
    assert attempt.restore
    assert drain.finalize_delivery(claim, delivered=True)
    return attempt.code


def expire(user):
    user.deletion_purge_after = timezone.now()
    user.save(update_fields=["deletion_purge_after"])


def email_row(user):
    return PasswordResetEnvelope.objects.get(user=user)

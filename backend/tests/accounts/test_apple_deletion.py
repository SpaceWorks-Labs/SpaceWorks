"""Verified Apple audience exchange, replacement and durable revocation."""

from datetime import timedelta
from unittest.mock import Mock

import pytest
from cryptography.fernet import Fernet
from django.utils import timezone

from apps.accounts import apple_credentials as credentials, apple_revocation as revocation
from apps.accounts.models import User, SocialIdentity
from apps.accounts.models_account_purge import AppleRefreshCredential, AppleRevocation
from apps.audit.models import AuditLog
from apps.makerspaces.secrets import decrypt_value, encrypt_value

pytestmark = pytest.mark.django_db


@pytest.fixture
def apple(settings, monkeypatch):
    settings.API_CLIENT_ENC_KEY = Fernet.generate_key().decode()
    user = User.objects.create_user(username="apple-member")
    identity = SocialIdentity.objects.create(user=user, provider="apple", provider_sub="apple-subject")
    monkeypatch.setattr(credentials, "client_secret", lambda client: "signed-client-secret")
    monkeypatch.setattr(revocation, "client_secret", lambda client: "signed-client-secret")
    return user, identity


def stored(identity, client="web.service", token="refresh-secret"):
    return AppleRefreshCredential.objects.create(social_identity=identity, client_id=client, token_ciphertext=encrypt_value(token))


def archive(user, days=1):
    user.deletion_requested_at = timezone.now() - timedelta(days=days)
    user.is_active = False
    user.save()


def test_exchange_uses_verified_aud_redirect_and_replaces_token(apple, monkeypatch):
    user, identity = apple
    exchange = Mock(return_value={"id_token": "exchanged-id", "refresh_token": "first-refresh"})
    monkeypatch.setattr(credentials, "apple_post", exchange)
    monkeypatch.setattr(credentials, "decode_rs256_token", lambda *args, **kwargs: {"sub": "apple-subject"})
    claims = {"sub": identity.provider_sub, "aud": "web.service"}
    credentials.store_refresh_credential(user, claims, "authorization-code", "https://app.example.test")
    row = AppleRefreshCredential.objects.get(social_identity=identity, client_id="web.service")
    assert row.token_ciphertext != "first-refresh" and decrypt_value(row.token_ciphertext) == "first-refresh"
    exchange.assert_called_once_with("/auth/token", {"client_id": "web.service", "client_secret": "signed-client-secret",
                                                     "grant_type": "authorization_code", "code": "authorization-code",
                                                     "redirect_uri": "https://app.example.test"})
    exchange.return_value["refresh_token"] = "replacement"
    credentials.store_refresh_credential(user, claims, "new-code")
    row.refresh_from_db()
    assert AppleRefreshCredential.objects.count() == 1 and decrypt_value(row.token_ciphertext) == "replacement"
    credentials.store_refresh_credential(user, {**claims, "aud": "native.bundle"}, "native-code")
    assert AppleRefreshCredential.objects.count() == 2


def test_exchange_subject_mismatch_and_outage_do_not_fail_signin(apple, monkeypatch):
    user, identity = apple
    monkeypatch.setattr(credentials, "apple_post", Mock(return_value={"id_token": "token", "refresh_token": "secret"}))
    monkeypatch.setattr(credentials, "decode_rs256_token", lambda *args, **kwargs: {"sub": "another-account"})
    credentials.store_refresh_credential(user, {"sub": identity.provider_sub, "aud": "web.service"}, "code")
    assert not AppleRefreshCredential.objects.exists()
    monkeypatch.setattr(credentials, "apple_post", Mock(side_effect=OSError("provider down")))
    credentials.store_refresh_credential(user, {"sub": identity.provider_sub, "aud": "web.service"}, "code")
    assert user.is_active and not AppleRefreshCredential.objects.exists()


def test_revocation_rows_commit_even_when_queue_is_unavailable(apple, monkeypatch, django_capture_on_commit_callbacks):
    from django.db import transaction
    user, identity = apple
    stored(identity)
    stored(identity, "native.bundle")
    archive(user)
    enqueue = Mock()
    monkeypatch.setattr(revocation, "_enqueue", enqueue)
    with django_capture_on_commit_callbacks(execute=False) as callbacks:
        with transaction.atomic():
            revocation.schedule_revocations(user)
            assert AppleRevocation.objects.filter(user=user, done_at__isnull=True).count() == 2
            enqueue.assert_not_called()
    assert len(callbacks) == 1
    assert AppleRevocation.objects.filter(user=user, done_at__isnull=True).count() == 2


def test_rollback_does_not_leave_revocation_work(apple, django_capture_on_commit_callbacks):
    from django.db import transaction
    user, identity = apple
    stored(identity)
    with django_capture_on_commit_callbacks(execute=False) as callbacks:
        with pytest.raises(RuntimeError), transaction.atomic():
            revocation.schedule_revocations(user)
            raise RuntimeError("departure rolled back")
    assert callbacks == [] and not AppleRevocation.objects.exists()


def test_revoke_failure_backoff_then_success_is_idempotent(apple, monkeypatch):
    user, identity = apple
    credential = stored(identity)
    archive(user)
    row = revocation.snapshot_credential(user, credential)
    revoke = Mock(side_effect=OSError("provider down"))
    monkeypatch.setattr(revocation, "apple_post", revoke)
    revocation.revoke_one(row.pk)
    row.refresh_from_db()
    assert row.attempts == 1 and row.last_error == "OSError" and row.next_attempt_at > timezone.now() and row.done_at is None
    revocation.revoke_one(row.pk)
    assert revoke.call_count == 1
    row.next_attempt_at = timezone.now() - timedelta(seconds=1)
    row.save()
    revoke.side_effect = None
    revocation.revoke_one(row.pk)
    row.refresh_from_db()
    assert row.done_at and not AppleRefreshCredential.objects.filter(pk=credential.pk).exists()
    assert revoke.call_args.args == ("/auth/revoke", {"client_id": "web.service", "client_secret": "signed-client-secret",
                                                      "token": "refresh-secret", "token_type_hint": "refresh_token"})
    revocation.revoke_one(row.pk)
    assert revoke.call_count == 2


@pytest.mark.parametrize("with_credential", [False, True])
def test_missing_credential_or_80_day_deadline_audits_unavailable(apple, monkeypatch, with_credential):
    user, identity = apple
    archive(user, days=81 if with_credential else 1)
    if with_credential:
        stored(identity)
    row = AppleRevocation.objects.create(user=user, client_id="web.service")
    revoke = Mock()
    monkeypatch.setattr(revocation, "apple_post", revoke)
    revocation.revoke_one(row.pk)
    row.refresh_from_db()
    assert row.done_at
    revoke.assert_not_called()
    assert AuditLog.objects.filter(action="account.apple_revocation_unavailable", target_id=str(user.pk)).count() == 1


def test_daily_sweep_recovers_legacy_no_credential_departure(apple, monkeypatch):
    user, _ = apple
    archive(user)
    revoke = Mock()
    monkeypatch.setattr(revocation, "apple_post", revoke)
    revocation.sweep_revocations()
    assert AppleRevocation.objects.get(user=user, client_id="").done_at
    revoke.assert_not_called()


def test_apple_verification_preserves_verified_audience(monkeypatch):
    from apps.accounts import social_apple
    monkeypatch.setattr(social_apple, "decode_rs256_token", lambda *args, **kwargs: {
        "sub": "subject", "aud": "verified-client", "nonce": "nonce", "email_verified": False,
    })
    assert social_apple.verify_apple_token("token", nonce="nonce", audience="verified-client")["aud"] == "verified-client"


def test_exchange_finishing_after_departure_is_queued_for_revocation(apple, monkeypatch, django_capture_on_commit_callbacks):
    user, identity = apple
    archive(user)
    monkeypatch.setattr(credentials, "apple_post", Mock(return_value={"id_token": "token", "refresh_token": "late-refresh"}))
    monkeypatch.setattr(credentials, "decode_rs256_token", lambda *args, **kwargs: {"sub": identity.provider_sub})
    enqueue = Mock()
    monkeypatch.setattr(revocation, "_enqueue", enqueue)
    with django_capture_on_commit_callbacks(execute=True):
        credentials.store_refresh_credential(user, {"sub": identity.provider_sub, "aud": "web.service"}, "code")
    assert AppleRefreshCredential.objects.get(social_identity=identity).client_id == "web.service"
    assert AppleRevocation.objects.get(user=user, client_id="web.service").done_at is None
    enqueue.assert_called_once_with(user.pk)

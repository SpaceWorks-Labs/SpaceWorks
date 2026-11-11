"""All Apple HTTP is mocked; durable work survives the post-commit queue gap."""

from datetime import timedelta
from unittest.mock import Mock

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts import account_deletion, apple_credentials as credentials, apple_revocation as revocation
from apps.accounts.models_account_purge import AppleRefreshCredential, AppleRevocation
from apps.accounts.models_social import PlatformSocialAuthSettings, SocialIdentity
from apps.audit.models import AuditLog
from apps.makerspaces.secrets import decrypt_value, encrypt_value
from tests.accounts.test_reauthentication import ORIGIN
from tests.accounts.test_support_m1d import account, due, m1d_config, proven, purge

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.fixture
def apple(monkeypatch):
    user = account()
    identity = SocialIdentity.objects.create(user=user, provider="apple", provider_sub="apple-subject")
    monkeypatch.setattr(credentials, "client_secret", lambda client: "signed:" + client)
    monkeypatch.setattr(revocation, "client_secret", lambda client: "signed:" + client)
    return user, identity


def apple_http(monkeypatch, *, status=200, payload=None):
    response = Mock(status_code=status)
    response.json.return_value = payload or {"id_token": "exchanged-token", "refresh_token": "refresh-secret"}
    response.__enter__ = Mock(return_value=response)
    response.__exit__ = Mock(return_value=False)
    post = Mock(return_value=response)
    monkeypatch.setattr(credentials.requests, "post", post)
    return post, response


def stored(identity, client="web.service"):
    return AppleRefreshCredential.objects.create(social_identity=identity, client_id=client,
        token_ciphertext=encrypt_value("refresh-secret"))


def test_apple_exchange_replaces_only_same_client_and_validates_verified_aud(apple, monkeypatch):
    user, identity = apple
    post, response = apple_http(monkeypatch)
    decoder = Mock(return_value={"sub": identity.provider_sub})
    monkeypatch.setattr(credentials, "decode_rs256_token", decoder)
    claims = {"sub": identity.provider_sub, "aud": "web.service"}
    credentials.store_refresh_credential(user, claims, "first-code", "https://app.example.test/callback")
    row = AppleRefreshCredential.objects.get(social_identity=identity, client_id="web.service")
    assert decrypt_value(row.token_ciphertext) == "refresh-secret" and row.token_ciphertext != "refresh-secret"
    assert post.call_args.args == ("https://appleid.apple.com/auth/token",)
    assert post.call_args.kwargs == {"data": {"client_id": "web.service", "client_secret": "signed:web.service",
        "code": "first-code", "grant_type": "authorization_code", "redirect_uri": "https://app.example.test/callback"},
        "timeout": 10, "allow_redirects": False}
    assert decoder.call_args.kwargs["audience"] == "web.service"
    response.json.return_value["refresh_token"] = "replacement"
    credentials.store_refresh_credential(user, claims, "replacement-code")
    row.refresh_from_db()
    assert decrypt_value(row.token_ciphertext) == "replacement"
    credentials.store_refresh_credential(user, {**claims, "aud": "native.bundle"}, "native-code")
    assert AppleRefreshCredential.objects.filter(social_identity=identity).count() == 2
    assert "redirect_uri" not in post.call_args.kwargs["data"]


@pytest.mark.parametrize("failure", ["sub_mismatch", "http", "network", "missing_refresh"])
def test_bad_exchange_preserves_previous_credential_and_does_not_fail_signin(apple, failure, monkeypatch):
    user, identity = apple
    old = stored(identity)
    before = old.token_ciphertext
    post, response = apple_http(monkeypatch, status=503 if failure == "http" else 200)
    if failure == "network":
        post.side_effect = OSError("provider unavailable")
    if failure == "missing_refresh":
        response.json.return_value.pop("refresh_token")
    monkeypatch.setattr(credentials, "decode_rs256_token", Mock(return_value={
        "sub": "another-person" if failure == "sub_mismatch" else identity.provider_sub}))
    assert credentials.store_refresh_credential(user, {"sub": identity.provider_sub, "aud": "web.service"}, "code") is None
    old.refresh_from_db()
    user.refresh_from_db()
    assert old.token_ciphertext == before and user.is_active
    assert AppleRefreshCredential.objects.count() == 1


def test_stage_a_commit_survives_crash_before_enqueue_and_daily_sweep_revokes_each_client(apple, monkeypatch):
    user, identity = apple
    stored(identity)
    stored(identity, "native.bundle")
    # Simulate the process going away before it can deliver the on_commit task.
    enqueue = Mock()
    monkeypatch.setattr(revocation, "_enqueue", enqueue)
    account_deletion.request_deletion(proven(user))
    user.refresh_from_db()
    assert not user.is_active
    enqueue.assert_called_once_with(user.pk)
    assert set(AppleRevocation.objects.filter(user=user, done_at__isnull=True).values_list("client_id", flat=True)) == {
        "web.service", "native.bundle"}
    post, _ = apple_http(monkeypatch)
    revocation.sweep_revocations(user.pk)
    assert AppleRevocation.objects.filter(user=user, done_at__isnull=False).count() == 2
    assert not AppleRefreshCredential.objects.filter(social_identity=identity).exists()
    assert post.call_count == 2
    for call in post.call_args_list:
        assert call.args == ("https://appleid.apple.com/auth/revoke",)
        assert call.kwargs["data"]["token"] == "refresh-secret"
        assert call.kwargs["data"]["token_type_hint"] == "refresh_token"
        assert call.kwargs["allow_redirects"] is False and call.kwargs["timeout"] == 10
    revocation.sweep_revocations(user.pk)
    assert post.call_count == 2
    assert AuditLog.objects.filter(action="account.apple_revoked", target_id=str(user.pk)).count() == 2


def test_revocation_failure_backoff_and_retry_block_global_purge_until_terminal(apple, monkeypatch):
    user, identity = apple
    stored(identity)
    # Still before the 80-day fallback, with a configurable shorter purge window.
    user.deletion_requested_at = timezone.now() - timedelta(days=1)
    user.deletion_purge_after = timezone.now() - timedelta(minutes=1)
    user.is_active = False
    user.save()
    row = revocation.snapshot_credential(user, AppleRefreshCredential.objects.get(social_identity=identity))
    post, response = apple_http(monkeypatch, status=503)
    revocation.revoke_one(row.pk)
    row.refresh_from_db()
    assert row.attempts == 1 and row.last_error == "ValueError" and row.next_attempt_at > timezone.now()
    assert row.done_at is None
    assert purge(user)["purged"] == 0 and user.email
    revocation.revoke_one(row.pk)
    assert post.call_count == 1
    row.next_attempt_at = timezone.now() - timedelta(seconds=1)
    row.save()
    response.status_code = 200
    revocation.revoke_one(row.pk)
    row.refresh_from_db()
    assert row.done_at and row.attempts == 2 and row.last_error == "" and row.next_attempt_at is None
    assert purge(user)["purged"] == 1
    assert AuditLog.objects.filter(action="account.apple_revocation_retry", target_id=str(user.pk)).count() == 1


@pytest.mark.parametrize("legacy", [True, False], ids=["no-credential", "80-day-deadline"])
def test_unavailable_revocation_is_audited_and_purge_can_finish(apple, legacy, monkeypatch):
    user, identity = apple
    if not legacy:
        stored(identity)
    due(user)
    if legacy:
        user.deletion_requested_at = timezone.now() - timedelta(days=1)
        user.save()
    post, _ = apple_http(monkeypatch)
    revocation.sweep_revocations(user.pk)
    row = AppleRevocation.objects.get(user=user)
    assert row.done_at and row.last_error == ("credential_unavailable" if legacy else "retention_deadline")
    post.assert_not_called()
    assert AuditLog.objects.filter(action="account.apple_revocation_unavailable", target_id=str(user.pk)).count() == 1
    assert purge(user)["purged"] == 1
    assert not AppleRefreshCredential.objects.filter(social_identity__user=user).exists()
    revocation.sweep_revocations(user.pk)
    assert AuditLog.objects.filter(action="account.apple_revocation_unavailable", target_id=str(user.pk)).count() == 1


def test_late_exchange_after_departure_adds_new_versioned_revocation(apple, monkeypatch):
    user, identity = apple
    due(user)
    row = AppleRevocation.objects.create(user=user, client_id="web.service", done_at=timezone.now())
    apple_http(monkeypatch)
    monkeypatch.setattr(credentials, "decode_rs256_token", Mock(return_value={"sub": identity.provider_sub}))
    enqueue = Mock()
    monkeypatch.setattr(revocation, "_enqueue", enqueue)
    credentials.store_refresh_credential(user, {"sub": identity.provider_sub, "aud": "web.service"}, "late-code")
    row.refresh_from_db()
    assert row.done_at is not None
    assert AppleRevocation.objects.filter(user=user, client_id="web.service", done_at__isnull=True).exists()
    assert AppleRefreshCredential.objects.filter(social_identity=identity, client_id="web.service").exists()
    enqueue.assert_called_once_with(user.pk)


@pytest.mark.parametrize("status", [200, 503], ids=["exchange-success", "exchange-unavailable"])
def test_real_apple_signin_passes_code_and_redirect_but_exchange_failure_keeps_login_successful(apple, status, monkeypatch):
    user, identity = apple
    configuration = PlatformSocialAuthSettings.load()
    configuration.apple_service_id = "web.service"
    configuration.save()
    post, _ = apple_http(monkeypatch, status=status)
    claims = {"sub": identity.provider_sub, "aud": "web.service", "email": user.email,
              "email_verified": True, "name": ""}
    monkeypatch.setattr("apps.accounts.views_social._verify", Mock(return_value=claims))
    monkeypatch.setattr(credentials, "decode_rs256_token", Mock(return_value={"sub": identity.provider_sub}))
    client = APIClient()
    data = {"surface": "member", "delivery": "web", "client_platform": "web"}
    nonce = client.post("/api/v1/auth/social/nonce", {"provider": "apple", **data},
        format="json", HTTP_ORIGIN=ORIGIN)
    assert nonce.status_code == 200
    result = client.post("/api/v1/auth/social/apple", {**data, "nonce": nonce.data["nonce"],
        "id_token": "signed-id-token", "authorization_code": "apple-code",
        "redirect_uri": ORIGIN + "/callback"}, format="json", HTTP_ORIGIN=ORIGIN)
    assert result.status_code == 200 and result.data["user"]["id"] == user.pk
    assert result.cookies["refresh_token"].value
    assert post.call_args.kwargs["data"]["code"] == "apple-code"
    assert post.call_args.kwargs["data"]["redirect_uri"] == ORIGIN + "/callback"
    assert AppleRefreshCredential.objects.filter(social_identity=identity).exists() is (status == 200)
    assert "apple-code" not in str(result.data) and "refresh-secret" not in str(result.data)

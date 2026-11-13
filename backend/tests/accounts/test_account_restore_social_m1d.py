"""Fresh linked-provider recovery and its deliberately non-restorable case."""

from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit
from unittest.mock import Mock

import pytest
from django.utils import timezone
from rest_framework.exceptions import AuthenticationFailed, PermissionDenied, ValidationError
from rest_framework.test import APIClient, APIRequestFactory

from apps.accounts import account_restore_social as service
from apps.accounts.account_restore import restore_disclosure
from apps.accounts.models import SocialIdentity, User
from apps.accounts.models_account_restore import AccountRestoreIntent
from apps.accounts.models_social import PlatformSocialAuthSettings
from apps.accounts.reauthentication_intents import _digest
from apps.audit.models import AuditLog
from tests.accounts.restore_helpers_m1d import archive, restore_config
from tests.accounts.test_support_m1d import account, m1d_config
from tests.accounts.test_reauthentication import ORIGIN

pytestmark = pytest.mark.django_db


def social_account(provider):
    user = account()
    user.email = ""
    user.save()
    SocialIdentity.objects.create(user=user, provider=provider, provider_sub="linked-subject")
    return archive(user)


def req(origin=ORIGIN):
    value = APIRequestFactory().post("/", {}, HTTP_ORIGIN=origin)
    value.auth = None
    return value


def start(user, provider, monkeypatch):
    monkeypatch.setattr(service, "_provider", lambda key: (None, "https://provider.example/authorize", "audience"))
    return service.start_social(req(), username=user.username, provider=provider, redirect_uri=ORIGIN + "/restore-callback")


@pytest.mark.parametrize("provider", ["apple", "google", "oidc:test"])
def test_fresh_linked_signin_restores_social_only_account_without_linking_or_sessions(provider, monkeypatch):
    user = social_account(provider)
    proof = start(user, provider, monkeypatch)
    claims = Mock(return_value={"sub": "linked-subject", "auth_time": timezone.now().timestamp()})
    monkeypatch.setattr(service, "provider_claims", claims)
    service.complete_social(req(), state=proof["state"], nonce=proof["nonce"], id_token="signed", code="code")
    user.refresh_from_db()
    assert user.is_active and not user.has_usable_password() and user.deletion_requested_at is None
    assert list(user.social_identities.values_list("provider", "provider_sub")) == [(provider, "linked-subject")]
    assert AuditLog.objects.filter(action="account.restored", target_id=str(user.pk)).exists()
    with pytest.raises(AuthenticationFailed):
        service.complete_social(req(), state=proof["state"], nonce=proof["nonce"], id_token="signed")
    assert claims.call_count == 1


@pytest.mark.parametrize("provider", ["apple", "google", "oidc:test"])
@pytest.mark.parametrize("age", [None, 301, -60, "invalid", True])
def test_no_second_factor_means_missing_stale_or_invalid_provider_auth_time_cannot_restore(provider, age, monkeypatch):
    user = social_account(provider)
    proof = start(user, provider, monkeypatch)
    value = timezone.now().timestamp() - age if type(age) in (int, float) else age
    monkeypatch.setattr(service, "provider_claims", lambda *a, **kw: {
        "sub": "linked-subject", "iat": timezone.now().timestamp(), "auth_time": value})
    with pytest.raises(AuthenticationFailed):
        service.complete_social(req(), state=proof["state"], nonce=proof["nonce"], id_token="silent-token")
    user.refresh_from_db()
    assert not user.is_active
    assert AccountRestoreIntent.objects.get(user=user).consumed_at


@pytest.mark.parametrize("provider", ["apple", "google", "oidc:test"])
def test_provider_requests_and_verifies_freshness_contract(provider, monkeypatch):
    user = social_account(provider)
    proof = start(user, provider, monkeypatch)
    query = parse_qs(urlsplit(proof["authorization_url"]).query)
    assert query["nonce"] == [proof["nonce"]] and query["state"] == [proof["state"]]
    if provider.startswith("oidc:"):
        assert query["prompt"] == ["login"] and query["max_age"] == ["0"]
        assert query["code_challenge_method"] == ["S256"]
    elif provider == "google":
        assert "auth_time" in query["claims"][0] and "prompt" not in query
    # Exercise the real provider dispatch for the built-ins, mocking only JWT verification.
    if provider in {"apple", "google"}:
        configuration = PlatformSocialAuthSettings.load()
        configuration.google_web_client_id = configuration.apple_service_id = "audience"
        configuration.save()
        parser = Mock(return_value={"sub": "linked-subject", "auth_time": timezone.now().timestamp()})
        monkeypatch.setattr(f"apps.accounts.social_{provider}.verify_{provider}_token", parser)
        service.complete_social(req(), state=proof["state"], nonce=proof["nonce"], id_token="signed")
        parser.assert_called_once_with("signed", nonce=proof["nonce"], audience="audience")


@pytest.mark.parametrize("tamper", ["nonce", "origin", "expired", "unlinked", "foreign_subject", "generation", "identifier", "purge"])
def test_social_restore_rechecks_issued_intent_and_locked_account(tamper, monkeypatch):
    user = social_account("google")
    proof = start(user, "google", monkeypatch)
    monkeypatch.setattr(service, "provider_claims", lambda *a, **kw: {
        "sub": "foreign" if tamper == "foreign_subject" else "linked-subject", "auth_time": timezone.now().timestamp()})
    if tamper == "expired":
        AccountRestoreIntent.objects.filter(user=user).update(expires_at=timezone.now())
    elif tamper == "unlinked":
        user.social_identities.all().delete()
    elif tamper == "generation":
        User.objects.filter(pk=user.pk).update(credential_generation=user.credential_generation + 1)
    elif tamper == "identifier":
        User.objects.filter(pk=user.pk).update(email="new-identity@example.test")
    elif tamper == "purge":
        User.objects.filter(pk=user.pk).update(purge_started_at=timezone.now())
    with pytest.raises((AuthenticationFailed, ValidationError)):
        service.complete_social(req("https://foreign.example" if tamper == "origin" else ORIGIN),
            state=proof["state"], nonce="foreign" if tamper == "nonce" else proof["nonce"], id_token="signed")
    user.refresh_from_db()
    assert not user.is_active and user.deletion_requested_at
    assert AccountRestoreIntent.objects.get(user=user).consumed_at


def test_github_only_disclosure_preflight_and_restore_refusal(monkeypatch):
    user = account(password=None)
    user.email = ""
    user.save()
    SocialIdentity.objects.create(user=user, provider="github", provider_sub="linked-subject")
    disclosure = restore_disclosure(user)
    assert disclosure["restorable"] is False and "cannot be restored" in disclosure["restore_reason"]
    client = APIClient()
    client.force_authenticate(user)
    result = client.get("/api/v1/auth/account/deletion", HTTP_ORIGIN=ORIGIN)
    assert result.status_code == 200 and result.data["restorable"] is False
    assert result.data["restore_reason"] == disclosure["restore_reason"]
    with pytest.raises(PermissionDenied):
        start(user, "github", monkeypatch)


def test_provider_start_unknown_and_known_have_same_shape_and_never_links(monkeypatch):
    user = social_account("google")
    one = start(user, "google", monkeypatch)
    unknown = SimpleNamespace(username="unknown-user")
    two = start(unknown, "google", monkeypatch)
    assert set(one) == set(two)
    row = AccountRestoreIntent.objects.get(token_digest=_digest(two["state"]))
    assert row.user_id is None
    monkeypatch.setattr(service, "provider_claims", lambda *a, **kw: {
        "sub": "linked-subject", "auth_time": timezone.now().timestamp()})
    with pytest.raises(AuthenticationFailed):
        service.complete_social(req(), state=two["state"], nonce=two["nonce"], id_token="signed")
    assert SocialIdentity.objects.count() == 1


def test_accounts_with_email_or_phone_must_use_their_recovery_channel(monkeypatch):
    user = archive()
    SocialIdentity.objects.create(user=user, provider="google", provider_sub="linked-subject")
    proof = start(user, "google", monkeypatch)
    monkeypatch.setattr(service, "provider_claims", lambda *a, **kw: {
        "sub": "linked-subject", "auth_time": timezone.now().timestamp()})
    with pytest.raises(AuthenticationFailed):
        service.complete_social(req(), state=proof["state"], nonce=proof["nonce"], id_token="signed")

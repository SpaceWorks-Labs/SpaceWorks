"""Exercise provider parsers and intent consumption before a real deletion."""

import importlib
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import Mock
from urllib.parse import parse_qs, urlsplit

import pytest
from django.utils import timezone
from rest_framework.exceptions import AuthenticationFailed, PermissionDenied

from apps.accounts import account_deletion, reauthentication as auth
from apps.accounts import reauthentication_intents as intents, reauthentication_factors as factors
from apps.accounts.mfa_crypto import totp
from apps.accounts.models_mfa import MFAChallenge
from apps.accounts.models_social import PlatformSocialAuthSettings, SocialIdentity
from tests.accounts.mfa_helpers import enrolled
from tests.accounts.test_reauthentication import ORIGIN, request
from tests.accounts.test_reauthentication_deletion import native_request
from tests.accounts.test_support_m1d import account, m1d_config

pytestmark = pytest.mark.django_db


def provider_flow(monkeypatch, user, provider, *, native=False, age=10, subject="linked", token_nonce=None):
    SocialIdentity.objects.create(user=user, provider=provider, provider_sub="linked")
    req = native_request(user)[0] if native else request(user, surface="member")
    config = SimpleNamespace(
        client_id=lambda key, platform: "native.aud" if platform != "web" else "web.aud",
        apple_native_app_ids=["test.app"], github_client_id="github-client",
    )
    if provider.startswith("oidc:"):
        config = SimpleNamespace(client_id="oidc-client", provider_key=provider,
            issuer="https://id.example.test", jwks_url="https://id.example.test/keys", allow_auto_link=False)
    monkeypatch.setattr(intents, "_provider", lambda key: (config, "https://id.example.test/auth", "web.aud"))
    exchange = Mock(return_value="signed-token")
    monkeypatch.setattr(intents, "discover", lambda row: {"token_endpoint": "https://id.example.test/token"})
    monkeypatch.setattr(intents, "exchange_code", exchange)
    started = intents.start_social(req, provider=provider, redirect_uri="" if native else ORIGIN + "/callback")
    claims = {"sub": subject, "nonce": token_nonce or started["nonce"], "iat": timezone.now().timestamp(),
              "aud": "test.app" if native and provider == "apple" else "web.aud"}
    if age is not None:
        claims["auth_time"] = timezone.now().timestamp() - age
    if provider == "github":
        parser = Mock(return_value=claims)
        monkeypatch.setattr("apps.accounts.github_http.github_claims", parser)
    else:
        module = importlib.import_module("apps.accounts.social_" + ("oidc" if provider.startswith("oidc:") else provider))
        parser = Mock(return_value=claims)
        monkeypatch.setattr(module, "decode_rs256_token", parser)
    return req, started, parser, exchange


def complete(req, started):
    return intents.complete_social(req, state=started["state"], nonce=started["nonce"],
                                   id_token="signed-token", code="oauth-code")


@pytest.mark.parametrize("provider", ["apple", "google", "oidc:lab"])
@pytest.mark.parametrize("native", [True, False], ids=["native", "web"])
def test_fresh_provider_proof_allows_deletion_and_uses_correct_audience(provider, native, monkeypatch):
    user = account(password=None)
    req, started, parser, exchange = provider_flow(monkeypatch, user, provider, native=native)
    assert complete(req, started)["verified"]
    with pytest.raises(AuthenticationFailed):
        complete(req, started)
    assert auth.require_recent_reauth(req).auth_time
    query = parse_qs(urlsplit(started["authorization_url"]).query)
    if provider == "google":
        assert "auth_time" in query["claims"][0]
        assert "prompt" not in query and "max_age" not in query
    elif provider.startswith("oidc:"):
        assert query["prompt"] == ["login"] and query["max_age"] == ["0"]
        assert query["code_challenge_method"] == ["S256"]
        exchange.assert_called_once()
    else:
        assert parser.call_args.kwargs["audience"] == ("test.app" if native else "web.aud")
    assert account_deletion.request_deletion(req)["deleted_at"]
    user.refresh_from_db()
    assert not user.is_active


@pytest.mark.parametrize("provider", ["apple", "oidc:lab"])
@pytest.mark.parametrize("age", [301, -60], ids=["stale", "future"])
def test_contradictory_auth_time_is_refused_and_consumption_commits(provider, age, monkeypatch):
    user = account(password=None)
    req, started, _, _ = provider_flow(monkeypatch, user, provider, age=age)
    with pytest.raises(AuthenticationFailed):
        complete(req, started)
    row = MFAChallenge.objects.get(token_digest=intents._digest(started["state"]))
    assert row.consumed_at
    with pytest.raises(AuthenticationFailed):
        complete(req, started)
    with pytest.raises(auth.RecentAuthenticationRequired):
        account_deletion.request_deletion(req)


@pytest.mark.parametrize("native", [True, False])
def test_apple_silent_id_token_with_only_iat_is_refused(native, monkeypatch):
    user = account(password=None)
    req, started, _, _ = provider_flow(monkeypatch, user, "apple", native=native, age=None)
    with pytest.raises(AuthenticationFailed):
        complete(req, started)
    assert auth.current(req) is None


@pytest.mark.parametrize("provider,age", [("google", None), ("google", 301), ("oidc:lab", None), ("github", None)])
@pytest.mark.parametrize("native", [True, False])
def test_missing_provider_freshness_needs_session_bound_email_code(provider, age, native, monkeypatch):
    user = account(password=None)
    delivered = Mock(return_value=SimpleNamespace(status="sent"))
    monkeypatch.setattr("apps.integrations.dispatch.dispatch_email", delivered)
    req, started, _, _ = provider_flow(monkeypatch, user, provider, native=native, age=age)
    result = complete(req, started)
    assert result["verified"] is False and result["factor_required"] == "email_code"
    with pytest.raises(auth.RecentAuthenticationRequired):
        account_deletion.request_deletion(req)
    token = result["factor_token"]
    row = MFAChallenge.objects.get(token_digest=intents._digest(token))
    assert row.context["parent_id"] == MFAChallenge.objects.get(token_digest=intents._digest(started["state"])).pk
    assert 590 < (row.expires_at - timezone.now()).total_seconds() <= 600
    assert delivered.call_args.kwargs["persist_body"] is False
    code = delivered.call_args.kwargs["text_body"].split(" is ")[1].split(".")[0]
    with pytest.raises(AuthenticationFailed):
        factors.confirm_factor(request(user, surface="member"), token=token, code=code)
    assert factors.confirm_factor(req, token=token, code=code)["verified"]
    with pytest.raises(AuthenticationFailed):
        factors.confirm_factor(req, token=token, code=code)
    assert account_deletion.request_deletion(req)["deleted_at"]


def test_github_without_any_second_factor_is_not_offered(monkeypatch):
    from apps.accounts.reauthentication_methods import methods
    user = account(password=None, verified=False)
    SocialIdentity.objects.create(user=user, provider="github", provider_sub="linked")
    configuration = PlatformSocialAuthSettings.load()
    configuration.github_client_id = "github-client"
    configuration.set_github_client_secret("github-secret")
    configuration.save()
    monkeypatch.setattr("apps.accounts.login_methods.social_login_enabled", lambda: True)
    monkeypatch.setattr("apps.accounts.login_methods.provider_login_enabled", lambda provider: True)
    monkeypatch.setattr(intents, "_provider", lambda key: (configuration, "https://github.com/auth", "github-client"))
    assert "github" not in methods(user)
    with pytest.raises(PermissionDenied):
        intents.start_social(request(user), provider="github", redirect_uri=ORIGIN + "/callback")
    assert not MFAChallenge.objects.filter(user=user).exists()


def test_github_plus_totp_is_sufficient_but_totp_cannot_be_replayed(monkeypatch):
    user = account(password=None)
    credential, secret = enrolled(user)
    req, started, _, _ = provider_flow(monkeypatch, user, "github", age=None)
    result = complete(req, started)
    assert result["factor_required"] == "totp"
    code = totp(secret, int(timezone.now().timestamp() // 30))
    assert factors.confirm_factor(req, token=result["factor_token"], code=code)["verified"]
    credential.refresh_from_db()
    assert credential.last_step >= 0
    with pytest.raises(AuthenticationFailed):
        auth.verify(request(user), code=code)
    assert account_deletion.request_deletion(req)["deleted_at"]


@pytest.mark.parametrize("defect", ["expired", "wrong_nonce", "foreign_subject"])
def test_social_proof_cannot_be_substituted_or_replayed(defect, monkeypatch):
    user = account(password=None)
    req, started, parser, _ = provider_flow(monkeypatch, user, "google",
        subject="foreign" if defect == "foreign_subject" else "linked",
        token_nonce="foreign-nonce" if defect == "wrong_nonce" else None)
    if defect == "expired":
        MFAChallenge.objects.filter(token_digest=intents._digest(started["state"])).update(
            expires_at=timezone.now() - timedelta(seconds=1))
    with pytest.raises(AuthenticationFailed):
        complete(req, started)
    assert auth.current(req) is None
    assert list(user.social_identities.values_list("provider_sub", flat=True)) == ["linked"]
    if defect == "expired":
        parser.assert_not_called()

"""Built-in providers offer enrollment fallback; OIDC keeps code + PKCE."""

import base64
import hashlib
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit

import pytest
from cryptography.fernet import Fernet
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied
from rest_framework.test import APIClient

from apps.accounts import reauthentication as service, reauthentication_intents as intents
from apps.accounts.models import User
from apps.accounts.models_mfa import MFAChallenge
from apps.accounts.models_oidc import OidcProvider
from apps.accounts.models_social import SocialIdentity
from apps.makerspaces.secrets import decrypt_value
from tests.accounts.test_reauthentication import ORIGIN, request

pytestmark = pytest.mark.django_db


@pytest.fixture
def actor(settings):
    settings.API_CLIENT_ENC_KEY = Fernet.generate_key().decode()
    settings.CORS_ALLOWED_ORIGINS = [ORIGIN]
    return User.objects.create_user(username="provider-fallback", email="fallback@example.test",
                                    email_verified_at=timezone.now())


@pytest.mark.parametrize("provider", ["google", "apple"])
def test_unconfigured_builtin_refuses_before_creating_intent(actor, provider):
    SocialIdentity.objects.create(user=actor, provider=provider, provider_sub="linked")
    req = request(actor)
    client = APIClient()
    client.force_authenticate(actor, token=req.auth)
    response = client.post("/api/v1/auth/reauth/social/start", {
        "provider": provider, "redirect_uri": ORIGIN + "/reauth/callback",
    }, format="json", HTTP_ORIGIN=ORIGIN)
    assert response.status_code == 503
    assert not MFAChallenge.objects.filter(user=actor).exists()
    with pytest.raises(PermissionDenied):
        service.require_recent_reauth(req)


def test_status_advertises_linked_builtin_and_oidc_verification(actor):
    for provider in ["google", "apple", "oidc:staff"]:
        SocialIdentity.objects.create(user=actor, provider=provider, provider_sub="linked")
    client = APIClient()
    client.force_authenticate(actor, token=request(actor).auth)
    response = client.get("/api/v1/auth/reauth", HTTP_ORIGIN=ORIGIN)
    assert response.status_code == 200
    assert set(response.data["providers"]) == {"google", "apple", "oidc:staff"}
    assert not response.data["password_available"]
    assert not response.data["mfa_enabled"]


@pytest.mark.parametrize("provider", ["google", "apple"])
def test_builtin_accounts_use_email_only_for_enrollment_not_step_up(actor, provider, monkeypatch):
    SocialIdentity.objects.create(user=actor, provider=provider, provider_sub="linked")
    delivered = {}

    def deliver(**kwargs):
        delivered.update(kwargs)
        return SimpleNamespace(status="sent")

    monkeypatch.setattr("apps.integrations.dispatch.dispatch_email", deliver)
    req = request(actor)
    assert intents.start_email(req) == {"sent": True}
    token = delivered["text_body"].split("#token=", 1)[1]
    assert intents.confirm_email(req, token) == {"confirmed": True}
    service.require_enrollment_proof(req)
    with pytest.raises(PermissionDenied):
        service.require_recent_reauth(req)


@pytest.mark.parametrize("provider", ["google", "apple"])
def test_outstanding_builtin_intents_cannot_complete_or_grant_proof(actor, provider):
    SocialIdentity.objects.create(user=actor, provider=provider, provider_sub="linked")
    req = request(actor)
    state, row = intents._new(req, "social_reauth", provider=provider, nonce="nonce")
    with pytest.raises(intents.ProviderUnavailable):
        intents.complete_social(req, state=state, nonce="nonce", id_token="old-provider-response")
    row.refresh_from_db()
    assert row.consumed_at
    assert not service.current(req)


def test_oidc_uses_query_code_pkce_and_verified_fresh_claims(actor, monkeypatch):
    provider = OidcProvider.objects.create(slug="staff", display_name="Staff",
        issuer="https://identity.example.test", jwks_url="https://identity.example.test/keys",
        client_id="staff-browser")
    SocialIdentity.objects.create(user=actor, provider="oidc:staff", provider_sub="linked")
    monkeypatch.setattr("apps.accounts.login_methods.social_login_enabled", lambda: True)
    monkeypatch.setattr(intents, "discover", lambda row: {
        "authorization_endpoint": "https://identity.example.test/auth"})
    req = request(actor)
    redirect = ORIGIN + "/reauth/callback"
    started = intents.start_social(req, provider="oidc:staff", redirect_uri=redirect)
    params = parse_qs(urlsplit(started["authorization_url"]).query)
    intent = MFAChallenge.objects.get(user=actor)
    verifier = decrypt_value(intent.pending_secret)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    assert params == {
        "client_id": [provider.client_id], "redirect_uri": [redirect], "scope": ["openid email"],
        "state": [started["state"]], "nonce": [started["nonce"]], "prompt": ["login"], "max_age": ["0"],
        "response_type": ["code"], "response_mode": ["query"],
        "code_challenge": [challenge], "code_challenge_method": ["S256"],
    }

    def exchange(row, document, **kwargs):
        assert row.pk == provider.pk
        assert kwargs == {"code": "authorization-code", "redirect_uri": redirect, "code_verifier": verifier}
        return "verified-id-token"

    def claims(token, *, nonce, provider_row):
        assert token == "verified-id-token" and nonce == started["nonce"]
        assert provider_row.pk == provider.pk
        return {"sub": "linked", "auth_time": timezone.now().timestamp()}

    monkeypatch.setattr(intents, "exchange_code", exchange)
    monkeypatch.setattr("apps.accounts.social_oidc.verify_oidc_token", claims)
    assert intents.complete_social(req, state=started["state"], nonce=started["nonce"],
                                   code="authorization-code")["verified"]
    assert service.require_recent_reauth(req)

"""Deletion proof must represent fresh identity, including native sessions."""

from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit

import pytest
from cryptography.fernet import Fernet
from django.utils import timezone
from rest_framework.exceptions import AuthenticationFailed, PermissionDenied

from apps.accounts import reauthentication as service, reauthentication_intents as intents
from apps.accounts import reauthentication_factors as factors, reauthentication_phone as phone
from apps.accounts.models import User
from apps.accounts.models_devices import DeviceGrant, DeviceRefreshFamily, NativeAppRegistration
from apps.accounts.models_mfa import MFAChallenge
from apps.accounts.models_social import SocialIdentity
from apps.accounts.models_phone import PhoneVerificationChallenge
from apps.accounts.reauthentication_providers import freshness
from apps.accounts.mfa_crypto import totp
from tests.accounts.mfa_helpers import enrolled
from tests.accounts.test_reauthentication import request, ORIGIN, PASSWORD

pytestmark = pytest.mark.django_db


@pytest.fixture
def actor(settings):
    settings.API_CLIENT_ENC_KEY = Fernet.generate_key().decode()
    settings.CORS_ALLOWED_ORIGINS = [ORIGIN]
    return User.objects.create_user(username="deletion-proof", email="delete@example.test",
                                    email_verified_at=timezone.now())


def provider_intent(actor, provider):
    SocialIdentity.objects.create(user=actor, provider=provider, provider_sub="linked")
    req = request(actor)
    raw, row = intents._new(req, "social_reauth", provider=provider, nonce="nonce")
    return req, raw, row


@pytest.mark.parametrize("provider,age,accepted", [
    ("apple", None, False), ("apple", 301, False), ("apple", 200, True),
    ("oidc:test", None, False), ("oidc:test", 301, False), ("oidc:test", 200, True),
    ("google", None, False), ("google", 301, False), ("google", 200, True),
])
def test_provider_freshness_rules(provider, age, accepted):
    value = timezone.now().timestamp() - age if age is not None else None
    if provider == "apple" and not accepted or provider.startswith("oidc:") and age == 301:
        from apps.accounts.social_jwt import SocialTokenError
        with pytest.raises(SocialTokenError):
            freshness(provider, value)
    else:
        assert freshness(provider, value) is accepted


def test_github_never_supplies_authentication_time_evidence():
    assert freshness("github", timezone.now().timestamp()) is False


@pytest.mark.parametrize("provider", ["google", "apple"])
def test_builtin_fresh_token_requires_already_linked_subject(actor, provider, monkeypatch):
    req, state, row = provider_intent(actor, provider)
    monkeypatch.setattr("apps.accounts.reauthentication_providers.provider_claims",
                        lambda *args, **kwargs: {"sub": "foreign", "auth_time": timezone.now().timestamp()})
    with pytest.raises(AuthenticationFailed):
        intents.complete_social(req, state=state, nonce="nonce", id_token="signed")
    row.refresh_from_db()
    assert row.consumed_at
    assert list(actor.social_identities.values_list("provider_sub", flat=True)) == ["linked"]
    assert not service.current(req)


@pytest.mark.parametrize("provider", ["github", "google", "oidc:test"])
def test_no_auth_time_requires_single_use_email_factor(actor, provider, monkeypatch):
    req, state, original = provider_intent(actor, provider)
    monkeypatch.setattr("apps.accounts.reauthentication_providers.provider_claims",
                        lambda *args, **kwargs: {"sub": "linked"})
    delivered = {}
    monkeypatch.setattr("apps.integrations.dispatch.dispatch_email",
                        lambda **kwargs: delivered.update(kwargs) or SimpleNamespace(status="sent"))
    result = intents.complete_social(req, state=state, nonce="nonce", code="provider-code")
    assert not result["verified"] and result["factor_required"] == "email_code"
    with pytest.raises(PermissionDenied):
        service.require_recent_reauth(req)
    challenge = MFAChallenge.objects.get(token_digest=intents._digest(result["factor_token"]))
    assert challenge.context["parent_id"] == original.pk
    assert 599 <= (challenge.expires_at - timezone.now()).total_seconds() <= 600
    code = delivered["text_body"].split(" is ")[1].split(".")[0]
    with pytest.raises(AuthenticationFailed):
        factors.confirm_factor(request(actor), token=result["factor_token"], code=code)
    assert factors.confirm_factor(req, token=result["factor_token"], code=code)["verified"]
    assert service.require_recent_reauth(req)
    with pytest.raises(AuthenticationFailed):
        factors.confirm_factor(req, token=result["factor_token"], code=code)
    with pytest.raises(AuthenticationFailed):
        intents.complete_social(req, state=state, nonce="nonce")


def test_email_factor_attempts_committed_and_capped(actor, monkeypatch):
    req, state, _ = provider_intent(actor, "github")
    monkeypatch.setattr("apps.accounts.reauthentication_providers.provider_claims", lambda *a, **k: {"sub": "linked"})
    monkeypatch.setattr("apps.integrations.dispatch.dispatch_email", lambda **k: SimpleNamespace(status="sent"))
    result = intents.complete_social(req, state=state, nonce="nonce")
    # Use a digest known never to match the supplied code.
    row = MFAChallenge.objects.get(token_digest=intents._digest(result["factor_token"]))
    row.context["code_digest"] = "0" * 64
    row.save(update_fields=["context"])
    for _ in range(5):
        with pytest.raises(AuthenticationFailed):
            factors.confirm_factor(req, token=result["factor_token"], code="123456")
    row.refresh_from_db()
    assert row.attempts == 5 and row.consumed_at
    assert not service.current(req)


def test_totp_takes_priority_and_replays_are_refused(actor, monkeypatch):
    req, state, _ = provider_intent(actor, "github")
    _, secret = enrolled(actor)
    # Intent must be made after MFA enrollment because the credential version binds it.
    state, _ = intents._new(req, "social_reauth", provider="github", nonce="nonce")
    monkeypatch.setattr("apps.accounts.reauthentication_providers.provider_claims", lambda *a, **k: {"sub": "linked"})
    result = intents.complete_social(req, state=state, nonce="nonce")
    assert result["factor_required"] == "totp"
    code = totp(secret, int(timezone.now().timestamp() // 30))
    assert factors.confirm_factor(req, token=result["factor_token"], code=code)["verified"]
    with pytest.raises(AuthenticationFailed):
        service.verify(request(actor), code=code)


def test_google_requests_auth_time_without_unsupported_prompt(actor, monkeypatch):
    SocialIdentity.objects.create(user=actor, provider="google", provider_sub="linked")
    monkeypatch.setattr(intents, "_provider", lambda _: (None, "https://accounts.google.com/auth", "aud"))
    result = intents.start_social(request(actor), provider="google", redirect_uri=ORIGIN + "/callback")
    query = parse_qs(urlsplit(result["authorization_url"]).query)
    assert "auth_time" in query["claims"][0]
    assert "prompt" not in query and "max_age" not in query


def native_request(actor):
    registration = NativeAppRegistration.objects.create(app_id="test.app", platform="apple", environment="production",
                                                        verifier_config_key="test", status="approved")
    grant = DeviceGrant.objects.create(user=actor, registration=registration, platform="apple", app_id="test.app",
                                       environment="production", attested_at=timezone.now(), last_used_at=timezone.now())
    family = DeviceRefreshFamily.objects.create(user=actor, grant=grant)
    req = request(actor, surface="member")
    req.META.pop("HTTP_ORIGIN")
    req.auth.update(device_grant_id=str(grant.pk), device_family_id=str(family.pk))
    req.device_grant = grant
    return req, family


def test_native_proof_binds_family_and_keeps_same_binding_after_refresh(actor):
    actor.set_password(PASSWORD)
    actor.save(update_fields=["password"])
    req, family = native_request(actor)
    assert service.verify(req, password=PASSWORD)["verified"]
    assert service.require_recent_reauth(req).session_id == "device:" + str(family.pk)
    intents._trusted_origin(req)
    other = DeviceRefreshFamily.objects.create(user=actor, grant=family.grant)
    req.auth["device_family_id"] = str(other.pk)
    with pytest.raises(PermissionDenied):
        service.require_recent_reauth(req)
    req.auth["device_family_id"] = str(family.pk)
    assert service.require_recent_reauth(req)
    family.revoked_at = timezone.now()
    family.save(update_fields=["revoked_at"])
    with pytest.raises(PermissionDenied):
        service.require_recent_reauth(req)


def test_phone_only_confirmation_and_failed_attempts(actor, monkeypatch):
    User.objects.filter(pk=actor.pk).update(phone_e164="+15551234567", phone_verified_at=timezone.now())
    actor.refresh_from_db()
    monkeypatch.setattr("apps.integrations.sms.sms_configured", lambda: True)
    monkeypatch.setattr("apps.accounts.services_phone.reserve_platform_otp_sms_quota", lambda: True)
    monkeypatch.setattr("apps.accounts.services_phone.send_sms", lambda **kwargs: True)
    monkeypatch.setattr("apps.accounts.services_phone._generate_otp", lambda: "654321")
    req = request(actor)
    result = phone.start(req)
    challenge = PhoneVerificationChallenge.objects.get(user=actor)
    assert challenge.purpose == "reauth"
    with pytest.raises(AuthenticationFailed):
        phone.confirm(req, token=result["token"], code="000000")
    challenge.refresh_from_db()
    assert challenge.failed_attempts == 1
    assert phone.confirm(req, token=result["token"], code="654321")["verified"]
    assert service.require_recent_reauth(req)
    with pytest.raises(AuthenticationFailed):
        phone.confirm(req, token=result["token"], code="654321")


@pytest.mark.parametrize("provider", ["google", "apple", "oidc"])
def test_verified_token_parsers_preserve_auth_time(provider, monkeypatch):
    import importlib
    module = importlib.import_module("apps.accounts.social_" + provider)
    timestamp = timezone.now().timestamp()
    monkeypatch.setattr(module, "decode_rs256_token", lambda *args, **kwargs:
                        {"sub": "linked", "nonce": "nonce", "aud": "aud", "auth_time": timestamp})
    if provider == "oidc":
        configuration = SimpleNamespace(provider_key="oidc:test", jwks_url="https://id.test/keys",
                                        issuer="https://id.test", client_id="aud", allow_auto_link=False)
        claims = module.verify_oidc_token("signed", nonce="nonce", provider_row=configuration)
    else:
        claims = getattr(module, "verify_" + provider + "_token")("signed", nonce="nonce", audience="aud")
    assert claims["auth_time"] == timestamp


def test_no_credentials_have_no_deletion_methods(actor):
    from apps.accounts.reauthentication_methods import methods
    actor.email_verified_at = None
    actor.save(update_fields=["email_verified_at"])
    assert methods(actor) == []


def test_phone_start_is_uniform_when_no_verified_phone_or_cooldown(actor, monkeypatch):
    req = request(actor)
    assert phone.start(req)["sent"] is True
    assert not PhoneVerificationChallenge.objects.filter(user=actor).exists()
    User.objects.filter(pk=actor.pk).update(phone_e164="+15551234567", phone_verified_at=timezone.now())
    actor.refresh_from_db()
    monkeypatch.setattr("apps.integrations.sms.sms_configured", lambda: True)
    from apps.accounts.services_phone import ChallengeCooldown
    def cooldown(*args, **kwargs):
        raise ChallengeCooldown()
    monkeypatch.setattr(phone, "_issue", cooldown)
    assert phone.start(req)["sent"] is True


def test_social_phone_factor_uses_exact_challenge_and_commits_failures(actor, monkeypatch):
    User.objects.filter(pk=actor.pk).update(phone_e164="+15551234567", phone_verified_at=timezone.now())
    actor.refresh_from_db()
    monkeypatch.setattr("apps.integrations.sms.sms_configured", lambda: True)
    monkeypatch.setattr("apps.accounts.services_phone.reserve_platform_otp_sms_quota", lambda: True)
    monkeypatch.setattr("apps.accounts.services_phone.send_sms", lambda **kwargs: True)
    monkeypatch.setattr("apps.accounts.services_phone._generate_otp", lambda: "654321")
    monkeypatch.setattr("apps.accounts.reauthentication_providers.provider_claims", lambda *a, **k: {"sub": "linked"})
    req, state, _ = provider_intent(actor, "github")
    result = intents.complete_social(req, state=state, nonce="nonce")
    assert result["factor_required"] == "phone"
    challenge = PhoneVerificationChallenge.objects.get(user=actor)
    with pytest.raises(AuthenticationFailed):
        factors.confirm_factor(req, token=result["factor_token"], code="000000")
    challenge.refresh_from_db()
    assert challenge.failed_attempts == 1
    assert factors.confirm_factor(req, token=result["factor_token"], code="654321")["verified"]

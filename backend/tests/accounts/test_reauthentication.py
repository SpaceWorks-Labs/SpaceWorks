from datetime import timedelta
from types import SimpleNamespace
import uuid

import pytest
from cryptography.fernet import Fernet
from django.contrib.auth.hashers import make_password
from django.utils import timezone
from rest_framework.exceptions import AuthenticationFailed, PermissionDenied
from rest_framework.test import APIRequestFactory, APIClient
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken

from apps.accounts import reauthentication as service, reauthentication_intents as intents
from apps.accounts.mfa_crypto import totp
from apps.accounts.models import User
from apps.accounts.models_mfa import MFAChallenge, UserMFA
from apps.accounts.models_reauthentication import ReauthenticationSession
from apps.accounts.models_social import SocialIdentity
from apps.accounts.tokens import SpaceWorksRefreshToken
from tests.accounts.mfa_helpers import enrolled

pytestmark = pytest.mark.django_db
PASSWORD = "Fresh verification password 492!"
ORIGIN = "http://localhost:5000"


@pytest.fixture(autouse=True)
def config(settings):
    settings.API_CLIENT_ENC_KEY = Fernet.generate_key().decode()
    settings.CORS_ALLOWED_ORIGINS = [ORIGIN]
    settings.PLATFORM_STAFF_ORIGINS = [ORIGIN]


@pytest.fixture
def user():
    return User.objects.create_user(username="reauth-user", password=PASSWORD,
                                   email="reauth@example.test", email_verified_at=timezone.now())


def request(user, *, surface=None, sid=None):
    from apps.accounts.surface_policy import token_kind
    kind = token_kind(user)
    surface = surface or ("platform" if kind == "platform" else "member")
    sid = sid or "session:" + str(uuid.uuid4())
    OutstandingToken.objects.get_or_create(jti=sid, defaults={"user": user, "token": "",
        "created_at": timezone.now(), "expires_at": timezone.now() + timedelta(days=1)})
    result = APIRequestFactory().post("/api/v1/auth/reauth", {}, HTTP_ORIGIN=ORIGIN)
    result.user = user
    result.auth = {"sid": sid, "surface": surface, "kind": kind,
                   "credential_generation": user.credential_generation}
    return result


def test_password_step_up_is_server_side_and_session_bound(user):
    one, two = request(user), request(user)
    with pytest.raises(PermissionDenied): service.require_recent_reauth(one)
    assert service.verify(one, password=PASSWORD)["verified"]
    proof = service.require_recent_reauth(one)
    assert proof.auth_time and proof.surface == "member"
    with pytest.raises(PermissionDenied): service.require_recent_reauth(two)
    assert "auth_time" not in one.auth
    assert ReauthenticationSession.objects.count() == 1


@pytest.mark.parametrize("change", ["surface", "generation", "password", "mfa", "expired", "future", "revoked"])
def test_all_proof_bindings_fail_closed(user, change, monkeypatch):
    req = request(user)
    service.verify(req, password=PASSWORD)
    proof = service.current(req)
    if change == "surface": req.auth["surface"] = "verification_only"
    elif change == "generation": monkeypatch.setattr(service, "current_auth_generation", lambda: "new-generation")
    elif change == "password":
        user.set_password("Changed password 929!"); user.save(update_fields=["password"])
        req.user.refresh_from_db()
    elif change == "mfa": enrolled(user)
    elif change == "expired":
        proof.auth_time = timezone.now() - timedelta(minutes=10, seconds=1); proof.save()
    elif change == "future":
        proof.auth_time = timezone.now() + timedelta(seconds=1); proof.save()
    elif change == "revoked": BlacklistedToken.objects.create(token=OutstandingToken.objects.get(jti=req.auth["sid"]))
    with pytest.raises((PermissionDenied, AuthenticationFailed)): service.require_recent_reauth(req)


def test_password_and_totp_both_required_and_replay_shared(user):
    row, secret = enrolled(user)
    req = request(user)
    code = totp(secret, int(timezone.now().timestamp() // 30))
    for password, value in [("wrong", code), (PASSWORD, "00000x"), (PASSWORD, "")]:
        with pytest.raises(AuthenticationFailed): service.verify(req, password=password, code=value)
    assert service.verify(req, password=PASSWORD, code=code)["verified"]
    with pytest.raises(AuthenticationFailed): service.verify(request(user), password=PASSWORD, code=code)
    row.refresh_from_db()
    assert row.last_step == int(timezone.now().timestamp() // 30)


def test_passwordless_totp_and_no_recovery_code(user):
    user.set_unusable_password(); user.save(update_fields=["password"])
    row, secret = enrolled(user, recovery_digests=[make_password("recovery-code")])
    req = request(user)
    with pytest.raises(AuthenticationFailed): service.verify(req, code="recovery-code")
    assert service.verify(req, code=totp(secret, int(timezone.now().timestamp() // 30)))["verified"]
    row.refresh_from_db(); assert len(row.recovery_digests) == 1


def test_passwordless_without_another_factor_and_native_refused(user):
    user.set_unusable_password(); user.save(update_fields=["password"])
    with pytest.raises(AuthenticationFailed): service.verify(request(user))
    req = request(user); req.auth["device_grant_id"] = str(uuid.uuid4())
    with pytest.raises(PermissionDenied): service.verify(req)


def social_intent(user, req):
    SocialIdentity.objects.create(user=user, provider="oidc:test", provider_sub="linked-subject")
    return intents._new(req, "social_reauth", provider="oidc:test", nonce="the-nonce", verifier="secret")


def mock_oidc_exchange(monkeypatch):
    provider = SimpleNamespace(client_id="aud")
    monkeypatch.setattr(intents, "_provider", lambda key: (provider, "https://provider.test/auth", "aud"))
    monkeypatch.setattr(intents, "discover", lambda row: {})
    monkeypatch.setattr(intents, "exchange_code", lambda *args, **kwargs: "signed")


@pytest.mark.parametrize("claims", [
    {"sub": "foreign-subject", "auth_time": "fresh"},
    {"sub": "linked-subject", "auth_time": True},
    {"sub": "linked-subject", "auth_time": 0},
])
def test_social_requires_verified_current_subject_and_fresh_auth_time(user, claims, monkeypatch):
    req = request(user); state, row = social_intent(user, req)
    mock_oidc_exchange(monkeypatch)
    monkeypatch.setattr("apps.accounts.social_oidc.verify_oidc_token", lambda *args, **kwargs: claims)
    with pytest.raises(AuthenticationFailed): intents.complete_social(req, state=state, nonce="the-nonce", id_token="signed")
    row.refresh_from_db(); assert row.consumed_at
    assert not service.current(req)


def test_social_intent_session_expiry_nonce_replay_and_mfa_afterward(user, monkeypatch):
    req = request(user); _, secret = enrolled(user)
    state, row = social_intent(user, req)
    mock_oidc_exchange(monkeypatch)
    monkeypatch.setattr("apps.accounts.social_oidc.verify_oidc_token", lambda *args, **kwargs:
                        {"sub": "linked-subject", "auth_time": timezone.now().timestamp()})
    with pytest.raises(AuthenticationFailed): intents.complete_social(request(user), state=state, nonce="the-nonce")
    result = intents.complete_social(req, state=state, nonce="the-nonce", id_token="signed")
    assert result["mfa_required"] and not result["verified"]
    with pytest.raises(PermissionDenied): service.require_recent_reauth(req)
    with pytest.raises(AuthenticationFailed): intents.complete_social(req, state=state, nonce="the-nonce")
    from apps.accounts.reauthentication_factors import confirm_factor
    assert confirm_factor(req, token=result["factor_token"], code=totp(secret, int(timezone.now().timestamp() // 30)))["verified"]


def test_email_enrollment_link_single_use_session_bound_and_never_full_step_up(user):
    user.set_unusable_password(); user.save(update_fields=["password"])
    req = request(user)
    token, row = intents._new(req, "enrollment_email")
    with pytest.raises(AuthenticationFailed): intents.confirm_email(request(user), token)
    assert intents.confirm_email(req, token)["confirmed"]
    service.require_enrollment_proof(req)
    with pytest.raises(PermissionDenied): service.require_recent_reauth(req)
    with pytest.raises(AuthenticationFailed): intents.confirm_email(req, token)
    assert not UserMFA.objects.filter(user=user).exists()


def test_refresh_does_not_extend_step_up_time(user):
    refresh = SpaceWorksRefreshToken.for_user(user)
    refresh["surface"] = "member"
    req = request(user, sid=refresh["sid"])
    service.verify(req, password=PASSWORD)
    before = service.current(req).auth_time
    from apps.accounts.web_sessions import extend_session
    from django.db import transaction
    with transaction.atomic(): extend_session(user, refresh)
    assert service.current(req).auth_time == before


def test_endpoint_no_store_throttle_and_explicit_code(user):
    req = request(user)
    client = APIClient(); client.force_authenticate(user, token=req.auth)
    result = client.post("/api/v1/auth/reauth", {"password": PASSWORD, "code": ""}, format="json")
    assert result.status_code == 200 and result["Cache-Control"] == "private, no-store"
    for _ in range(6): client.post("/api/v1/auth/reauth", {"password": "wrong"}, format="json")
    assert client.post("/api/v1/auth/reauth", {}, format="json").status_code == 429


def test_link_unlink_changes_credential_version_and_cannot_resurrect_proof(user):
    req = request(user)
    SocialIdentity.objects.create(user=user, provider="google", provider_sub="same-subject")
    service.verify(req, password=PASSWORD)
    SocialIdentity.objects.filter(user=user).delete()
    with pytest.raises(PermissionDenied): service.require_recent_reauth(req)
    SocialIdentity.objects.create(user=user, provider="google", provider_sub="same-subject")
    with pytest.raises(PermissionDenied): service.require_recent_reauth(req)


def test_completed_social_without_mfa_cannot_extend_auth_time_with_empty_post(user, monkeypatch):
    req = request(user); state, _ = social_intent(user, req)
    mock_oidc_exchange(monkeypatch)
    monkeypatch.setattr("apps.accounts.social_oidc.verify_oidc_token", lambda *args, **kwargs:
                        {"sub": "linked-subject", "auth_time": timezone.now().timestamp()})
    assert intents.complete_social(req, state=state, nonce="the-nonce", id_token="signed")["verified"]
    proof = service.require_recent_reauth(req); before = proof.auth_time
    with pytest.raises(AuthenticationFailed): service.verify(req)
    assert service.current(req).auth_time == before
    service.require_enrollment_proof(req)


def test_unlinked_identity_between_provider_verification_and_final_lock_refused(user, monkeypatch):
    req = request(user); state, _ = social_intent(user, req)
    mock_oidc_exchange(monkeypatch)
    def provider(*args, **kwargs):
        SocialIdentity.objects.filter(user=user).delete()
        return {"sub": "linked-subject", "auth_time": timezone.now().timestamp()}
    monkeypatch.setattr("apps.accounts.social_oidc.verify_oidc_token", provider)
    with pytest.raises(AuthenticationFailed): intents.complete_social(req, state=state, nonce="the-nonce", id_token="signed")
    assert not service.current(req)


@pytest.mark.parametrize("seconds", [-301, 1])
def test_social_authentication_time_five_minute_window(user, seconds, monkeypatch):
    req = request(user); state, _ = social_intent(user, req)
    mock_oidc_exchange(monkeypatch)
    monkeypatch.setattr("apps.accounts.social_oidc.verify_oidc_token", lambda *args, **kwargs:
                        {"sub": "linked-subject", "auth_time": timezone.now().timestamp() + seconds})
    with pytest.raises(AuthenticationFailed): intents.complete_social(req, state=state, nonce="the-nonce", id_token="signed")


def test_social_wrong_nonce_consumes_attempt_and_expired_intent_is_refused(user):
    req = request(user); state, row = social_intent(user, req)
    with pytest.raises(AuthenticationFailed): intents.complete_social(req, state=state, nonce="wrong-nonce")
    row.refresh_from_db(); assert row.consumed_at
    state, row = intents._new(req, "social_reauth", provider="google", nonce="fresh")
    row.expires_at = timezone.now() - timedelta(seconds=1); row.save()
    with pytest.raises(AuthenticationFailed): intents.complete_social(req, state=state, nonce="fresh")


def test_email_failure_invalidates_intent_and_does_not_grant_enrollment(user, monkeypatch):
    user.set_unusable_password(); user.save(update_fields=["password"])
    req = request(user)
    monkeypatch.setattr(intents, "_trusted_origin", lambda request: None)
    monkeypatch.setattr("apps.integrations.dispatch.dispatch_email", lambda **kwargs: SimpleNamespace(status="failed"))
    with pytest.raises(intents.ProviderUnavailable): intents.start_email(req)
    assert MFAChallenge.objects.filter(user=user, consumed_at__isnull=False).count() == 1
    with pytest.raises(PermissionDenied): service.require_enrollment_proof(req)


def test_optional_secret_fields_accept_explicit_empty_values():
    from apps.accounts.serializers_reauthentication import ReauthenticationSerializer, ReauthenticationSocialCompleteSerializer
    from apps.accounts.serializers_mfa import MFAEnrollmentStartSerializer
    for cls, data in [
        (ReauthenticationSerializer, {"password": "", "code": "123456"}),
        (ReauthenticationSerializer, {"password": PASSWORD, "code": ""}),
        (ReauthenticationSocialCompleteSerializer, {"state": "state", "nonce": "nonce", "code": "", "id_token": "signed", "totp": ""}),
        (ReauthenticationSocialCompleteSerializer, {"state": "state", "nonce": "nonce", "code": "code", "id_token": "", "totp": ""}),
        (MFAEnrollmentStartSerializer, {"password": ""}),
    ]:
        serializer = cls(data=data)
        assert serializer.is_valid(), serializer.errors

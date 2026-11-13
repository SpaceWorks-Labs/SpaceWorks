from datetime import timedelta

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.attestation import challenge_digest
from apps.accounts.models import (
    DeviceAttestationChallenge,
    DeviceGrant,
    SocialLoginNonce,
    User,
)
from apps.accounts.models_social import PlatformSocialAuthSettings
from apps.accounts.services_device_tokens import issue_device_token_pair
from apps.accounts.social_jwt import SocialTokenError
from apps.accounts.social_nonces import nonce_digest
from apps.audit.models import AuditLog
from tests.device_helpers import make_native_app_registration
from tests.return_helpers import make_space, make_user


pytestmark = pytest.mark.django_db
CHALLENGE_URL = "/api/v1/auth/device/attestation-challenge"
NONCE_URL = "/api/v1/auth/social/nonce"
LOGIN_URL = "/api/v1/auth/social/google"
APP_ID = "org.spaceworks.app"
APP_ID_PREFIX = "TEAMID1234"
# Deliberately NOT the app id. An OAuth client id and an attested bundle identifier are
# different namespaces, and a fixture that set them equal was what hid a check requiring
# them to match -- which would have rejected every real Google native first login.
OAUTH_AUDIENCE = "1234567890-abcdef.apps.googleusercontent.com"

def configure_native_social(settings, *, audience=OAUTH_AUDIENCE):
    settings.DEVICE_APPLE_ATTESTATION_VERIFY_URL = "https://attest.example.test/verify"
    settings.DEVICE_APPLE_ATTESTATION_VERIFY_TOKEN = "provider-secret"
    registration = make_native_app_registration(app_id=APP_ID)
    # Phase 1e stores the App ID Prefix separately from the bundle identifier.
    registration.signing_identities = [APP_ID_PREFIX]
    registration.save(update_fields=["signing_identities", "updated_at"])
    social = PlatformSocialAuthSettings.load()
    social.google_ios_client_id = audience
    social.google_android_client_id = audience
    social.save(update_fields=[
        "google_ios_client_id", "google_android_client_id", "updated_at"])
    return registration

def issue_challenge(client):
    response = client.post(
        CHALLENGE_URL,
        {"platform": "apple", "app_id": APP_ID, "environment": "development"},
        format="json",
    )
    assert response.status_code == 200
    return response.data["challenge"]

def create_challenge(registration, raw, **overrides):
    values = {
        "registration": registration,
        "platform": "apple",
        "app_id": APP_ID,
        "signing_identity": APP_ID_PREFIX,
        "environment": "development",
        "challenge_digest": challenge_digest(raw),
        "expires_at": timezone.now() + timedelta(minutes=5),
    }
    values.update(overrides)
    return DeviceAttestationChallenge.objects.create(**values)

def request_nonce(client, challenge=None, *, client_platform="ios"):
    payload = {
        "provider": "google",
        "surface": "member",
        "delivery": "device",
        "client_platform": client_platform,
    }
    if challenge is not None:
        payload["challenge"] = challenge
    return client.post(NONCE_URL, payload, format="json")

def complete_login(client, nonce, challenge, *, client_platform="ios", id_token="provider-token"):
    return client.post(
        LOGIN_URL,
        {
            "id_token": id_token,
            "nonce": nonce,
            "surface": "member",
            "delivery": "device",
            "client_platform": client_platform,
            "challenge": challenge,
            "attestation": {"assertion": "opaque"},
        },
        format="json",
    )

def mock_identity(monkeypatch, user):
    monkeypatch.setattr(
        "apps.accounts.views_social._verify",
        lambda *args, **kwargs: {
            "sub": f"sub-{user.pk}",
            "email": user.email,
            "email_verified": True,
            "name": user.username,
        },
    )

def mock_attestation(monkeypatch, raw):
    class Response:
        status_code = 200

        def json(self):
            return {
                "verified": True,
                "subject": "attested-device-subject",
                "platform": "apple",
                "app_id": APP_ID,
                "signing_identity": APP_ID_PREFIX,
                "environment": "development",
                "challenge": raw,
            }

    monkeypatch.setattr(
        "apps.accounts.attestation_apple.requests.post",
        lambda *args, **kwargs: Response(),
    )

def test_social_login_creates_first_attested_grant(settings, monkeypatch):
    configure_native_social(settings)
    user = make_user(
        "social-first-grant",
        access_status=User.AccessStatus.ACTIVE,
        email_verified_at=timezone.now(),
    )
    challenge = issue_challenge(APIClient())
    nonce = request_nonce(APIClient(), challenge)
    assert nonce.status_code == 200
    mock_identity(monkeypatch, user)
    mock_attestation(monkeypatch, challenge)

    response = complete_login(APIClient(), nonce.data["nonce"], challenge)

    assert response.status_code == 200
    assert {"access", "refresh", "device_grant"} <= set(response.data)
    grant = DeviceGrant.objects.get(user=user)
    assert grant.registration.app_id == APP_ID
    assert grant.attestation_subject_fingerprint != "attested-device-subject"
    assert jwt.decode(
        response.data["access"], options={"verify_signature": False}
    )["device_grant_id"] == str(grant.pk)
    assert DeviceAttestationChallenge.objects.get(
        challenge_digest=challenge_digest(challenge)
    ).consumed_at is not None
    assert AuditLog.objects.filter(
        actor=user, action="auth.device_login_succeeded").exists()

def test_native_nonce_without_grant_or_challenge_is_rejected(settings):
    configure_native_social(settings)
    assert request_nonce(APIClient()).status_code == 400

@pytest.mark.parametrize("status", ["pending", "revoked"])
def test_unapproved_registration_cannot_back_nonce(settings, status):
    registration = configure_native_social(settings)
    raw = f"challenge-{status}"
    create_challenge(registration, raw)
    registration.status = status
    registration.save(update_fields=["status", "updated_at"])

    assert request_nonce(APIClient(), raw).status_code == 403

@pytest.mark.parametrize("state", ["expired", "consumed"])
def test_spent_challenge_cannot_back_nonce(settings, state):
    registration = configure_native_social(settings)
    raw = f"challenge-{state}"
    overrides = (
        {"expires_at": timezone.now() - timedelta(seconds=1)}
        if state == "expired"
        else {"consumed_at": timezone.now()}
    )
    create_challenge(registration, raw, **overrides)

    assert request_nonce(APIClient(), raw).status_code == 403

def test_different_challenge_is_rejected_at_consumption(settings):
    registration = configure_native_social(settings)
    first, second = "bound-challenge", "substitute-challenge"
    create_challenge(registration, first)
    create_challenge(registration, second)
    nonce = request_nonce(APIClient(), first).data["nonce"]

    response = complete_login(APIClient(), nonce, second)

    assert response.status_code == 409
    assert response.data["code"] == "social_device_restart_required"

def test_challenge_from_different_registration_is_rejected(settings):
    registration = configure_native_social(settings)
    bound = "registration-bound-challenge"
    create_challenge(registration, bound)
    nonce = request_nonce(APIClient(), bound).data["nonce"]
    other = make_native_app_registration(
        app_id=APP_ID, makerspace=make_space("other-native-registration")
    )
    substitute = "other-registration-challenge"
    create_challenge(other, substitute)

    response = complete_login(APIClient(), nonce, substitute)

    assert response.status_code == 409
    assert response.data["code"] == "social_device_restart_required"

def test_client_platform_must_match_challenge(settings):
    registration = configure_native_social(settings)
    raw = "platform-mismatch"
    create_challenge(registration, raw)
    nonce = request_nonce(APIClient(), raw).data["nonce"]
    response = complete_login(APIClient(), nonce, raw, client_platform="android")
    assert (response.status_code, response.data["code"]) == (
        409, "social_device_restart_required")

def test_provider_audience_must_match_registration(settings, monkeypatch):
    from apps.accounts.social_google import verify_google_token

    configure_native_social(settings)
    challenge = issue_challenge(APIClient())
    nonce = request_nonce(APIClient(), challenge).data["nonce"]
    mock_attestation(monkeypatch, challenge)
    # The OAuth audience must match provider configuration, not the attested bundle
    # ID. Use a valid signed token for another client so this exercises audience
    # verification rather than merely rejecting the old opaque placeholder token.
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    monkeypatch.setattr(
        "apps.accounts.social_jwt._key_for_kid",
        lambda *args, **kwargs: private_key.public_key(),
    )
    other_audience = "other-client.apps.googleusercontent.com"
    now = int(timezone.now().timestamp())
    token = jwt.encode(
        {"iss": "https://accounts.google.com", "aud": other_audience,
         "sub": "audience-mismatch", "nonce": nonce, "iat": now, "exp": now + 300},
        private_key, algorithm="RS256", headers={"kid": "test-google-key"},
    )
    assert verify_google_token(token, nonce=nonce, audience=other_audience)["sub"] == "audience-mismatch"

    response = complete_login(APIClient(), nonce, challenge, id_token=token)

    assert response.status_code == 409
    assert response.data["code"] == "social_device_restart_required"
    assert not DeviceGrant.objects.exists()
    assert SocialLoginNonce.objects.get(nonce_digest=nonce_digest(nonce)).consumed_at is not None

def test_provider_failure_burns_nonce_and_requires_fresh_start(settings, monkeypatch):
    configure_native_social(settings)
    challenge = issue_challenge(APIClient())
    raw_nonce = request_nonce(APIClient(), challenge).data["nonce"]
    mock_attestation(monkeypatch, challenge)

    def reject_provider(*args, **kwargs):
        raise SocialTokenError("rejected")

    monkeypatch.setattr("apps.accounts.views_social._verify", reject_provider)
    failed = complete_login(APIClient(), raw_nonce, challenge)
    retry = complete_login(APIClient(), raw_nonce, challenge)

    assert failed.status_code == retry.status_code == 409
    assert failed.data["code"] == retry.data["code"] == (
        "social_device_restart_required"
    )
    assert SocialLoginNonce.objects.get(
        nonce_digest=nonce_digest(raw_nonce)
    ).consumed_at is not None

def test_nonce_constraint_rejects_both_native_anchors(settings):
    registration = configure_native_social(settings)
    challenge = create_challenge(registration, "constraint-challenge")
    user = make_user("constraint-user", access_status=User.AccessStatus.ACTIVE)
    now = timezone.now()
    grant = DeviceGrant.objects.create(
        registration=registration, user=user, platform="apple", app_id=APP_ID,
        signing_identity=APP_ID_PREFIX, environment="development",
        attestation_subject_fingerprint="f" * 64, attested_at=now,
        last_used_at=now,
    )

    with pytest.raises(IntegrityError), transaction.atomic():
        SocialLoginNonce.objects.create(
            provider="google", surface="member", delivery="device",
            client_platform="ios", nonce_digest="d" * 64,
            device_grant=grant, attestation_challenge=challenge,
            expires_at=now + timedelta(minutes=5),
        )

def test_existing_grant_bound_social_login_still_works(settings, monkeypatch):
    registration = configure_native_social(settings)
    user = make_user(
        "existing-social-grant", access_status=User.AccessStatus.ACTIVE,
        email_verified_at=timezone.now(),
    )
    now = timezone.now()
    grant = DeviceGrant.objects.create(
        registration=registration, user=user, platform="apple", app_id=APP_ID,
        signing_identity=APP_ID_PREFIX, environment="development",
        attestation_subject_fingerprint="f" * 64, attested_at=now,
        last_used_at=now,
    )
    access, _refresh, _family = issue_device_token_pair(user, grant)
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
    mock_identity(monkeypatch, user)
    nonce = request_nonce(client)
    response = client.post(
        LOGIN_URL,
        {"id_token": "provider-token", "nonce": nonce.data["nonce"],
         "surface": "member", "delivery": "device", "client_platform": "ios"},
        format="json",
    )

    assert response.status_code == 200
    assert response.data["device_grant"]["id"] == str(grant.pk)
    assert DeviceGrant.objects.filter(user=user).count() == 1

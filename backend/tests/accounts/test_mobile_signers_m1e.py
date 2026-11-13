"""A rotated Play distribution signer survives every native grant-creation path."""

import base64
import hashlib
from unittest.mock import Mock

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.attestation import AttestationRejected, create_challenge, verify_attestation
from apps.accounts.attestation_play_integrity import verify_play_integrity
from apps.accounts.mfa_crypto import totp
from apps.accounts.models_attestation import PlatformAttestationSettings
from apps.accounts.models_devices import DeviceAttestationChallenge, DeviceGrant
from apps.accounts.models_social import PlatformSocialAuthSettings, SocialIdentity
from tests.accounts.mfa_helpers import enrolled
from tests.accounts.mobile_integration_helpers import APP, FIRST, SECOND, registration
from tests.accounts.test_phone_auth_p8 import (
    LOGIN_CONFIRM, LOGIN_START, NUMBER, code_from, sms_on, verified_member,
)
from tests.accounts.test_social_first_grant import OAUTH_AUDIENCE, mock_identity

pytestmark = pytest.mark.django_db


def verdict(raw, digest=SECOND):
    return {"tokenPayloadExternal": {
        "requestDetails": {
            "requestHash": base64.urlsafe_b64encode(hashlib.sha256(raw.encode()).digest()).rstrip(b"=").decode(),
            "requestPackageName": APP, "timestampMillis": int(timezone.now().timestamp() * 1000),
        },
        "appIntegrity": {"appRecognitionVerdict": "PLAY_RECOGNIZED",
                         "certificateSha256Digest": [base64.urlsafe_b64encode(bytes.fromhex(digest)).rstrip(b"=").decode()]},
        "deviceIntegrity": {"deviceRecognitionVerdict": ["MEETS_DEVICE_INTEGRITY"]},
    }}


@pytest.fixture
def android(settings, monkeypatch):
    settings.DEVICE_ATTESTATION_APPS = {}
    settings.DEVICE_ANDROID_ATTESTATION_VERIFY_URL = ""
    settings.DEVICE_ANDROID_ATTESTATION_VERIFY_TOKEN = ""
    settings.DEVICE_ATTESTATION_DEV_INSECURE = False
    row = registration()
    PlatformAttestationSettings.objects.create(pk=1, play_integrity_service_account="encrypted-configured-marker")
    # Provider decoding is the network seam. All local request binding, signer matching
    # and grant metadata propagation execute unchanged.
    monkeypatch.setattr("apps.accounts.attestation_play_integrity._decode", lambda package, token: verdict(token))
    return row


def attestation_fields(raw):
    return {"challenge": raw, "attestation": {"type": "play_integrity", "token": raw}}


@pytest.mark.parametrize("method", ["password", "social", "phone"])
@pytest.mark.parametrize("mfa", [False, True])
def test_rotated_signer_is_recorded_through_password_social_phone_and_mfa(
    android, monkeypatch, sms_on, method, mfa,
):
    user = verified_member()
    if mfa:
        _, secret = enrolled(user)
    raw = create_challenge(platform="android", app_id=APP, environment="production")
    challenge = DeviceAttestationChallenge.objects.latest("pk")
    assert challenge.signing_identity == FIRST
    assert challenge.signing_identities == [FIRST, SECOND]
    client = APIClient()
    if method == "password":
        result = client.post("/api/v1/auth/device/login", {
            "username": user.username, "password": "pw-strong-123", "platform": "android",
            "app_id": APP, "environment": "production", **attestation_fields(raw),
        }, format="json")
    elif method == "social":
        social = PlatformSocialAuthSettings.load()
        social.google_android_client_id = OAUTH_AUDIENCE
        social.save()
        # A linked provider subject authenticates this existing phone account;
        # an email match alone cannot take over its unverified local address.
        SocialIdentity.objects.create(user=user, provider="google", provider_sub=f"sub-{user.pk}")
        nonce = client.post("/api/v1/auth/social/nonce", {
            "provider": "google", "surface": "member", "delivery": "device",
            "client_platform": "android", "challenge": raw,
        }, format="json")
        assert nonce.status_code == 200
        mock_identity(monkeypatch, user)
        result = client.post("/api/v1/auth/social/google", {
            "id_token": "opaque-google-token", "nonce": nonce.data["nonce"], "surface": "member",
            "delivery": "device", "client_platform": "android", **attestation_fields(raw),
        }, format="json")
    else:
        start = client.post(LOGIN_START, {"phone": NUMBER, "delivery": "device",
                            "client_platform": "android", "challenge": raw}, format="json")
        assert start.status_code == 200 and sms_on
        result = client.post(LOGIN_CONFIRM, {"phone": NUMBER, "code": code_from(sms_on),
                             "delivery": "device", "client_platform": "android", **attestation_fields(raw)}, format="json")
    assert result.status_code == 200, result.data
    if mfa and method != "social":
        assert result.data["mfa_required"]
        result = client.post("/api/v1/auth/mfa/verify", {
            "challenge": result.data["challenge"],
            "code": totp(secret, int(timezone.now().timestamp() // 30)),
        }, format="json")
        assert result.status_code == 200, result.data
    assert DeviceGrant.objects.get(user=user).signing_identity == SECOND


def test_unknown_signer_cannot_create_a_verified_identity(android, monkeypatch):
    raw = create_challenge(platform="android", app_id=APP, environment="production")
    challenge = DeviceAttestationChallenge.objects.latest("pk")
    monkeypatch.setattr("apps.accounts.attestation_play_integrity._decode", lambda *args: verdict(raw, "ef" * 32))
    with pytest.raises(AttestationRejected):
        verify_play_integrity(challenge, raw, {"type": "play_integrity", "token": raw})


def test_external_verifier_contract_keeps_exactly_one_scalar_signer(android, settings, monkeypatch):
    settings.DEVICE_ANDROID_ATTESTATION_VERIFY_URL = "https://verifier.example.test/verify"
    settings.DEVICE_ANDROID_ATTESTATION_VERIFY_TOKEN = "private-verifier-token"
    raw = create_challenge(platform="android", app_id=APP, environment="production")
    challenge = DeviceAttestationChallenge.objects.latest("pk")
    response = Mock(status_code=200)
    response.json.return_value = {"verified": True, "subject": "external-device", "platform": "android",
                                  "app_id": APP, "environment": "production",
                                  "signing_identity": FIRST, "challenge": raw}
    post = Mock(return_value=response)
    monkeypatch.setattr("apps.accounts.attestation_apple.requests.post", post)
    verified = verify_attestation(challenge, raw, {"assertion": "opaque"})
    assert verified.metadata["signing_identity"] == FIRST
    body = post.call_args.kwargs["json"]
    assert body["signing_identity"] == FIRST
    assert "signing_identities" not in body

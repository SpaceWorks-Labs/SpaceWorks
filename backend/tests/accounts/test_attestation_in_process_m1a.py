"""Play Integrity Standard verification, including the real OAuth exchange seam."""

import base64
import hashlib
import json
from types import SimpleNamespace
from unittest.mock import Mock, patch

import jwt
import pytest
import requests
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from django.utils import timezone

from apps.accounts.attestation import AttestationRejected, AttestationUnavailable
from apps.accounts.attestation_play_integrity import verify_play_integrity
from apps.accounts.models_attestation import PlatformAttestationSettings

pytestmark = pytest.mark.django_db
PACKAGE = "org.spaceworks.app"
DIGEST = "ab" * 32
RAW = "play-standard-challenge"
PAYLOAD = {"type": "play_integrity", "token": "opaque-integrity-token"}


@pytest.fixture(scope="module")
def google_key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture
def google_account(settings, google_key):
    settings.API_CLIENT_ENC_KEY = Fernet.generate_key().decode()
    settings.DEVICE_ATTESTATION_CHALLENGE_TTL_SECONDS = 180
    private = google_key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()
    row = PlatformAttestationSettings.load()
    row.set_play_integrity_service_account(json.dumps({
        "type": "service_account", "client_email": "attest@example.iam.gserviceaccount.com",
        "private_key": private,
    }))
    row.save()
    return row


def challenge(environment="production"):
    return SimpleNamespace(platform="android", app_id=PACKAGE,
                           signing_identity=DIGEST, environment=environment)


def verdict():
    return {"tokenPayloadExternal": {
        "requestDetails": {
            "requestHash": base64.urlsafe_b64encode(
                hashlib.sha256(RAW.encode()).digest(),
            ).rstrip(b"=").decode(),
            "requestPackageName": PACKAGE,
            "timestampMillis": str(int(timezone.now().timestamp() * 1000)),
        },
        "appIntegrity": {
            "appRecognitionVerdict": "PLAY_RECOGNIZED",
            "certificateSha256Digest": [base64.urlsafe_b64encode(
                bytes.fromhex(DIGEST),
            ).rstrip(b"=").decode()],
        },
        "deviceIntegrity": {"deviceRecognitionVerdict": ["MEETS_DEVICE_INTEGRITY"]},
    }}


def response(data, status=200):
    return Mock(status_code=status, json=Mock(return_value=data))


def test_valid_play_integrity_binds_oauth_package_challenge_and_certificate(
    google_account, google_key, settings,
):
    with patch("apps.accounts.attestation_google.requests.post", side_effect=[
        response({"access_token": "google-access"}), response(verdict()),
    ]) as post:
        verified = verify_play_integrity(challenge(), RAW, PAYLOAD)

    assert verified.subject == f"{PACKAGE}:{DIGEST}"
    assert verified.metadata == {"package": PACKAGE, "certificate_digest": DIGEST,
                                 "signing_identity": DIGEST}
    assert post.call_count == 2
    oauth, decode = post.call_args_list
    assert oauth.args == ("https://oauth2.googleapis.com/token",)
    assert oauth.kwargs["data"]["grant_type"] == "urn:ietf:params:oauth:grant-type:jwt-bearer"
    claims = jwt.decode(oauth.kwargs["data"]["assertion"], google_key.public_key(),
                        algorithms=["RS256"], audience="https://oauth2.googleapis.com/token")
    assert claims["iss"] == "attest@example.iam.gserviceaccount.com"
    assert claims["scope"] == "https://www.googleapis.com/auth/playintegrity"
    assert decode.args == (f"https://playintegrity.googleapis.com/v1/{PACKAGE}:decodeIntegrityToken",)
    assert decode.kwargs["json"] == {"integrity_token": PAYLOAD["token"]}
    assert decode.kwargs["headers"] == {"Authorization": "Bearer google-access"}
    for call in (oauth, decode):
        assert call.kwargs["timeout"] == settings.DEVICE_ATTESTATION_PROVIDER_TIMEOUT_SECONDS
        assert call.kwargs["allow_redirects"] is False


@pytest.mark.parametrize("failure", [
    "request_hash", "package", "stale", "unrecognized", "certificate", "device_integrity",
])
def test_play_integrity_rejects_each_failed_verdict_check(google_account, settings, failure):
    data = verdict()
    claims = data["tokenPayloadExternal"]
    if failure == "request_hash":
        claims["requestDetails"]["requestHash"] = "wrong-request-hash"
    elif failure == "package":
        claims["requestDetails"]["requestPackageName"] = "org.attacker.app"
    elif failure == "stale":
        stale = timezone.now().timestamp() - settings.DEVICE_ATTESTATION_CHALLENGE_TTL_SECONDS - 60
        claims["requestDetails"]["timestampMillis"] = str(int(stale * 1000))
    elif failure == "unrecognized":
        claims["appIntegrity"]["appRecognitionVerdict"] = "UNRECOGNIZED_VERSION"
    elif failure == "certificate":
        claims["appIntegrity"]["certificateSha256Digest"] = ["cd" * 32]
    else:
        claims["deviceIntegrity"]["deviceRecognitionVerdict"] = ["MEETS_BASIC_INTEGRITY"]
    with patch("apps.accounts.attestation_google.requests.post", side_effect=[
        response({"access_token": "google-access"}), response(data),
    ]):
        with pytest.raises(AttestationRejected):
            verify_play_integrity(challenge(), RAW, PAYLOAD)


def test_play_development_registration_does_not_require_play_recognized(google_account):
    data = verdict()
    data["tokenPayloadExternal"]["appIntegrity"]["appRecognitionVerdict"] = "UNEVALUATED"
    with patch("apps.accounts.attestation_google.requests.post", side_effect=[
        response({"access_token": "google-access"}), response(data),
    ]):
        verified = verify_play_integrity(challenge("development"), RAW, PAYLOAD)
    assert verified.subject == f"{PACKAGE}:{DIGEST}"
    assert verified.metadata["package"] == PACKAGE


@pytest.mark.parametrize("stage", ["oauth", "decode"])
@pytest.mark.parametrize("failure", ["503", "timeout"])
def test_google_outages_are_unavailable_not_bad_attestations(google_account, stage, failure):
    unavailable = response({}, 503) if failure == "503" else requests.Timeout("offline")
    replies = [unavailable] if stage == "oauth" else [
        response({"access_token": "google-access"}), unavailable,
    ]
    with patch("apps.accounts.attestation_google.requests.post", side_effect=replies):
        with pytest.raises(AttestationUnavailable):
            verify_play_integrity(challenge(), RAW, PAYLOAD)

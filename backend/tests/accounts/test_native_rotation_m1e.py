"""Real Play verdict validation and matched-signer propagation through API logins."""

import base64
import hashlib
from unittest.mock import Mock

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.attestation import AttestationRejected, verify_attestation
from apps.accounts.attestation_play_integrity import verify_play_integrity
from apps.accounts.mfa_crypto import totp
from apps.accounts.models import DeviceAttestationChallenge, DeviceGrant
from apps.accounts.models_social import PlatformSocialAuthSettings
from tests.accounts.mfa_helpers import enrolled
from tests.accounts.test_attestation_in_process_m1a import (
    DIGEST, PACKAGE, google_account, google_key, response, verdict,
)
from tests.accounts.test_device_auth import CHALLENGE, LOGIN
from tests.accounts.test_native_config_m1a import mock_identity
from tests.accounts.test_phone_auth_p8 import (
    LOGIN_CONFIRM, LOGIN_START, NUMBER, code_from, sms_on, verified_member,
)
from tests.accounts.test_social_first_grant import request_nonce
from tests.device_helpers import make_native_app_registration

pytestmark = pytest.mark.django_db
ROTATED = "cd" * 32


@pytest.fixture
def rotation(settings, google_account):
    settings.DEVICE_ATTESTATION_APPS = {}
    settings.DEVICE_ANDROID_ATTESTATION_VERIFY_URL = ""
    settings.DEVICE_ANDROID_ATTESTATION_VERIFY_TOKEN = ""
    settings.DEVICE_ATTESTATION_DEV_INSECURE = False
    row = make_native_app_registration(platform="android", environment="production")
    row.signing_identities = [DIGEST, ROTATED]
    row.save(update_fields=["signing_identities"])
    return row


def issue_android_challenge(client):
    result = client.post(CHALLENGE, {
        "platform": "android", "app_id": PACKAGE, "environment": "production",
    }, format="json")
    assert result.status_code == 200, result.data
    return result.data["challenge"]


def play_verdict(raw, signer):
    data = verdict()
    claims = data["tokenPayloadExternal"]
    claims["requestDetails"]["requestHash"] = base64.urlsafe_b64encode(
        hashlib.sha256(raw.encode()).digest(),
    ).rstrip(b"=").decode()
    claims["appIntegrity"]["certificateSha256Digest"] = [
        base64.urlsafe_b64encode(bytes.fromhex(signer)).rstrip(b"=").decode(),
    ]
    return data


@pytest.mark.parametrize("signer", [DIGEST, ROTATED], ids=["original-signer", "rotated-signer"])
@pytest.mark.parametrize("method", ["password", "mfa", "social", "phone", "phone_mfa"])
def test_android_matched_signer_is_persisted_by_each_grant_creation_path(
    rotation, monkeypatch, sms_on, method, signer,
):
    user = verified_member("m1e-rotation-user")
    user.email_verified_at = timezone.now()
    user.save(update_fields=["email_verified_at"])
    if method in {"mfa", "phone_mfa"}:
        _, secret = enrolled(user)
    client = APIClient()
    raw = issue_android_challenge(client)
    challenge = DeviceAttestationChallenge.objects.get(registration=rotation)
    assert challenge.signing_identity == DIGEST
    assert challenge.signing_identities == [DIGEST, ROTATED]
    # Mock HTTP only: OAuth, request binding, signer matching and grant creation run.
    post = Mock(side_effect=[response({"access_token": "m1e-google-access"}),
                             response(play_verdict(raw, signer))])
    monkeypatch.setattr("apps.accounts.attestation_google.requests.post", post)
    proof = {"challenge": raw, "attestation": {"type": "play_integrity", "token": "opaque"}}
    if method in {"password", "mfa"}:
        result = client.post(LOGIN, {
            "username": user.username, "password": "pw-strong-123", "platform": "android",
            "app_id": PACKAGE, "environment": "production", **proof,
        }, format="json")
    elif method == "social":
        social = PlatformSocialAuthSettings.load()
        social.google_android_client_id = "native-rotation.apps.googleusercontent.com"
        social.save()
        nonce = request_nonce(client, raw, client_platform="android")
        assert nonce.status_code == 200, nonce.data
        mock_identity(monkeypatch, user)
        result = client.post("/api/v1/auth/social/google", {
            "id_token": "m1e-google-id-token", "nonce": nonce.data["nonce"],
            "surface": "member", "delivery": "device", "client_platform": "android", **proof,
        }, format="json")
    else:
        start = client.post(LOGIN_START, {
            "phone": NUMBER, "delivery": "device", "client_platform": "android", "challenge": raw,
        }, format="json")
        assert start.status_code == 200 and sms_on
        result = client.post(LOGIN_CONFIRM, {
            "phone": NUMBER, "code": code_from(sms_on), "delivery": "device",
            "client_platform": "android", **proof,
        }, format="json")
    assert result.status_code == 200, result.data
    if method in {"mfa", "phone_mfa"}:
        assert result.data["mfa_required"] is True
        assert not DeviceGrant.objects.filter(user=user).exists()
        assert "access" not in result.data
        # The signer must survive server-owned MFA context, not a client assertion.
        result = client.post("/api/v1/auth/mfa/verify", {
            "challenge": result.data["challenge"],
            "code": totp(secret, int(timezone.now().timestamp() // 30)),
        }, format="json")
        assert result.status_code == 200, result.data
    assert post.call_count == 2
    grant = DeviceGrant.objects.get(user=user)
    assert str(grant.pk) == result.data["device_grant"]["id"]
    assert grant.signing_identity == signer
    assert grant.registration_id == rotation.pk
    challenge.refresh_from_db()
    assert challenge.consumed_at is not None


def test_play_verdict_can_contain_unrelated_digest_before_the_matching_rotated_digest(rotation, monkeypatch):
    raw = issue_android_challenge(APIClient())
    challenge = DeviceAttestationChallenge.objects.get(registration=rotation)
    data = play_verdict(raw, ROTATED)
    data["tokenPayloadExternal"]["appIntegrity"]["certificateSha256Digest"].insert(0, "ef" * 32)
    monkeypatch.setattr("apps.accounts.attestation_play_integrity._decode", lambda *args: data)
    verified = verify_play_integrity(challenge, raw, {"type": "play_integrity", "token": "opaque"})
    assert verified.metadata["signing_identity"] == ROTATED
    assert verified.metadata["certificate_digest"] == ROTATED


def test_unregistered_digest_is_rejected(rotation, monkeypatch):
    raw = issue_android_challenge(APIClient())
    challenge = DeviceAttestationChallenge.objects.get(registration=rotation)
    monkeypatch.setattr("apps.accounts.attestation_play_integrity._decode",
                        lambda *args: play_verdict(raw, "ef" * 32))
    with pytest.raises(AttestationRejected):
        verify_play_integrity(challenge, raw, {"type": "play_integrity", "token": "opaque"})


def test_challenge_keeps_the_complete_signer_snapshot_after_registration_is_edited(rotation, monkeypatch):
    raw = issue_android_challenge(APIClient())
    challenge = DeviceAttestationChallenge.objects.get(registration=rotation)
    rotation.signing_identities = ["ef" * 32]
    rotation.save(update_fields=["signing_identities"])
    challenge.refresh_from_db()
    assert challenge.signing_identity == DIGEST
    assert challenge.signing_identities == [DIGEST, ROTATED]
    monkeypatch.setattr("apps.accounts.attestation_play_integrity._decode", lambda *args: play_verdict(raw, ROTATED))
    verified = verify_play_integrity(challenge, raw, {"type": "play_integrity", "token": "opaque"})
    assert verified.metadata["signing_identity"] == ROTATED


def test_external_verifier_receives_only_the_first_scalar_signer(rotation, settings, monkeypatch):
    settings.DEVICE_ANDROID_ATTESTATION_VERIFY_URL = "https://external.example.test/verify"
    settings.DEVICE_ANDROID_ATTESTATION_VERIFY_TOKEN = "external-private-token"
    raw = issue_android_challenge(APIClient())
    challenge = DeviceAttestationChallenge.objects.get(registration=rotation)
    provider = Mock(return_value=response({
        "verified": True, "subject": "external-subject", "platform": "android", "app_id": PACKAGE,
        "environment": "production", "signing_identity": DIGEST, "challenge": raw,
    }))
    monkeypatch.setattr("apps.accounts.attestation_apple.requests.post", provider)
    verified = verify_attestation(challenge, raw, {"assertion": "opaque"})
    body = provider.call_args.kwargs["json"]
    assert body == {
        "challenge": raw, "platform": "android", "app_id": PACKAGE, "signing_identity": DIGEST,
        "environment": "production", "attestation": {"assertion": "opaque"},
    }
    assert verified.metadata["signing_identity"] == DIGEST
    assert challenge.signing_identities == [DIGEST, ROTATED]

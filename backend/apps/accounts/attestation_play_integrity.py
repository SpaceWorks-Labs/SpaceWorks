"""Verify Play Integrity STANDARD request verdicts; never accept Classic nonces."""

import base64
import binascii
import hashlib
import hmac
import logging
import re
from urllib.parse import quote

import requests
from django.conf import settings
from django.utils import timezone

from apps.accounts.attestation import AttestationRejected, AttestationUnavailable, VerifiedAttestation
from apps.accounts.attestation_google import service_account_access_token

logger = logging.getLogger(__name__)


def certificate_digest(value):
    """Canonical hex SHA-256, accepting Google's base64url and console hex forms."""
    if not isinstance(value, str):
        raise ValueError("Invalid certificate digest")
    hex_value = value.replace(":", "")
    if re.fullmatch(r"[0-9a-fA-F]{64}", hex_value):
        return hex_value.lower()
    raw = base64.b64decode(value + "=" * (-len(value) % 4), altchars=b"-_", validate=True)
    if len(raw) != 32:
        raise ValueError("Invalid certificate digest")
    return raw.hex()


def _decode(package, token):
    access_token = service_account_access_token()
    try:
        response = requests.post(
            f"https://playintegrity.googleapis.com/v1/{quote(package, safe='')}:decodeIntegrityToken",
            json={"integrity_token": token},
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=settings.DEVICE_ATTESTATION_PROVIDER_TIMEOUT_SECONDS,
            allow_redirects=False,
        )
        if response.status_code >= 500 or response.status_code in {401, 403, 408, 429}:
            raise AttestationUnavailable("Device attestation is unavailable.")
        if response.status_code != 200:
            raise AttestationRejected("Attestation was rejected.")
        data = response.json()
    except (requests.RequestException, ValueError) as exc:
        logger.warning("Attestation decode unavailable", extra={"provider": "play_integrity"})
        raise AttestationUnavailable("Device attestation is unavailable.") from exc
    except AttestationUnavailable:
        logger.warning("Attestation decode unavailable", extra={"provider": "play_integrity", "http_status": response.status_code})
        raise
    return data


def verify_play_integrity(challenge, raw_challenge, payload):
    if (not isinstance(payload, dict) or payload.get("type") != "play_integrity"
            or not isinstance(payload.get("token"), str) or not 0 < len(payload["token"]) <= 65536):
        raise AttestationRejected("Attestation was rejected.")
    data = _decode(challenge.app_id, payload["token"])
    try:
        claims = data["tokenPayloadExternal"]
        details = claims["requestDetails"]
        expected_hash = base64.urlsafe_b64encode(hashlib.sha256(raw_challenge.encode()).digest()).rstrip(b"=").decode()
        timestamp = int(details["timestampMillis"]) / 1000
        if (not hmac.compare_digest(details["requestHash"], expected_hash)
                or details["requestPackageName"] != challenge.app_id
                or abs(timezone.now().timestamp() - timestamp) > settings.DEVICE_ATTESTATION_CHALLENGE_TTL_SECONDS):
            raise ValueError("Request binding failed")
        app = claims.get("appIntegrity", {})
        digests = [certificate_digest(value) for value in app.get("certificateSha256Digest", [])]
        expected_digest = certificate_digest(challenge.signing_identity)
        if challenge.environment == "production" and (
            app.get("appRecognitionVerdict") != "PLAY_RECOGNIZED" or expected_digest not in digests
        ):
            raise ValueError("App identity failed")
        verdicts = claims["deviceIntegrity"]["deviceRecognitionVerdict"]
        if not isinstance(verdicts, list) or "MEETS_DEVICE_INTEGRITY" not in verdicts:
            raise ValueError("Device integrity failed")
        digest = expected_digest if expected_digest in digests else next(iter(digests), expected_digest)
    except (KeyError, TypeError, ValueError, AttributeError, OverflowError, binascii.Error) as exc:
        raise AttestationRejected("Attestation was rejected.") from exc
    return VerifiedAttestation(
        subject=f"{challenge.app_id}:{digest}",
        metadata={"package": challenge.app_id, "certificate_digest": digest},
    )

"""Google service-account JWT bearer exchange, with bounded provider I/O."""

import json
import logging
import time

import jwt
import requests
from cryptography.fernet import InvalidToken
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from apps.accounts.attestation import AttestationUnavailable
from apps.accounts.models_attestation import PlatformAttestationSettings

logger = logging.getLogger(__name__)
TOKEN_URL = "https://oauth2.googleapis.com/token"


def service_account_access_token():
    try:
        row = PlatformAttestationSettings.objects.filter(pk=1).first()
        account = json.loads(row.get_play_integrity_service_account()) if row else {}
        if account.get("type") != "service_account" or not account.get("client_email"):
            raise ValueError("Invalid service account")
        now = int(time.time())
        assertion = jwt.encode({
            "iss": account["client_email"],
            "scope": "https://www.googleapis.com/auth/playintegrity",
            "aud": TOKEN_URL, "iat": now, "exp": now + 3600,
        }, account["private_key"], algorithm="RS256")
    except (InvalidToken, ImproperlyConfigured, KeyError, ValueError, TypeError, AttributeError, jwt.PyJWTError) as exc:
        logger.warning("Attestation credential unavailable", extra={"provider": "play_integrity"})
        raise AttestationUnavailable("Device attestation is unavailable.") from exc
    try:
        response = requests.post(
            TOKEN_URL,
            data={"grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer", "assertion": assertion},
            timeout=settings.DEVICE_ATTESTATION_PROVIDER_TIMEOUT_SECONDS,
            allow_redirects=False,
        )
        if response.status_code != 200:
            raise ValueError("OAuth exchange failed")
        data = response.json()
        token = data.get("access_token")
        if not isinstance(token, str) or not token:
            raise ValueError("Missing access token")
        return token
    except (requests.RequestException, ValueError, AttributeError) as exc:
        logger.warning("Attestation OAuth exchange unavailable", extra={"provider": "play_integrity"})
        raise AttestationUnavailable("Device attestation is unavailable.") from exc

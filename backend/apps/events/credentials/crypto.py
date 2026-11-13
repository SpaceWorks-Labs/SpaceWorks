"""Opaque SWEC2 payloads. Key material is deployment-owned, never portable PII."""

import base64
import hashlib
import hmac
import re
import secrets
from dataclasses import dataclass, field

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from django.conf import settings

from .errors import CredentialKeyUnavailable

PAYLOAD = re.compile(r"^SWEC2\.([A-Za-z0-9_-]{43})$")
DOMAIN = b"event-registration:v2"


@dataclass(frozen=True)
class CredentialMaterial:
    digest: str = field(repr=False)
    ciphertext: bytes = field(repr=False)
    key_version: int


def _key(value):
    try:
        key = base64.b64decode(value, validate=True)
        if len(key) != 32:
            raise ValueError()
        return key
    except (TypeError, ValueError) as exc:
        raise CredentialKeyUnavailable() from exc


def _aad(event_id, registration_id, generation):
    return b":".join((DOMAIN, str(event_id).encode(), str(registration_id).encode(),
                      str(generation).encode()))


def token_digest(event_id, payload):
    if not isinstance(payload, str) or not PAYLOAD.fullmatch(payload):
        return None
    key = _key(getattr(settings, "EVENT_REGISTRATION_CREDENTIAL_DIGEST_KEY", None))
    return hmac.new(key, DOMAIN + b":" + str(event_id).encode() + b":" + payload.encode(),
                    hashlib.sha256).hexdigest()


def prepare(event_id, registration_id, generation):
    payload = "SWEC2." + secrets.token_urlsafe(32)
    version = getattr(settings, "EVENT_REGISTRATION_CREDENTIAL_KEY_VERSION", None)
    keys = getattr(settings, "EVENT_REGISTRATION_CREDENTIAL_KEYS", {})
    key = _key(keys.get(str(version)))
    nonce = secrets.token_bytes(12)
    ciphertext = nonce + AESGCM(key).encrypt(
        nonce, payload.encode(), _aad(event_id, registration_id, generation),
    )
    return CredentialMaterial(token_digest(event_id, payload), ciphertext, version)


def unwrap(credential, event_id):
    keys = getattr(settings, "EVENT_REGISTRATION_CREDENTIAL_KEYS", {})
    try:
        value = bytes(credential.token_ciphertext)
        payload = AESGCM(_key(keys.get(str(credential.key_version)))).decrypt(
            value[:12], value[12:],
            _aad(event_id, credential.registration_id, credential.generation),
        ).decode("ascii")
        if not hmac.compare_digest(token_digest(event_id, payload), credential.token_digest):
            raise ValueError()
        return payload
    except CredentialKeyUnavailable:
        raise
    except Exception as exc:
        raise CredentialKeyUnavailable() from exc

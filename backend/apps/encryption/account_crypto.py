"""Always-encrypted AES-256-GCM account envelopes with owner/row/field AAD."""

import secrets

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from apps.encryption.brokers.base import require_dek
from apps.encryption.crypto import (
    PiiAuthenticationFailed, PiiMalformedEnvelope, PiiUnavailable, _decode, _encode,
)

PREFIX = "pii:account:gcm:v1:"


def is_envelope(raw):
    return isinstance(raw, str) and raw.startswith(PREFIX)


def aad(user_id, table, pk, field):
    if not isinstance(user_id, int) or user_id <= 0 or pk is None:
        raise PiiUnavailable()
    if any(not isinstance(value, str) or not value or ":" in value for value in (table, field)):
        raise PiiUnavailable()
    return f"account:{user_id}:{table}:{pk}:{field}".encode("utf-8")


def parse_envelope(raw):
    if not is_envelope(raw):
        raise PiiMalformedEnvelope()
    parts = raw.split(":")
    if len(parts) != 7 or parts[:4] != ["pii", "account", "gcm", "v1"]:
        raise PiiMalformedEnvelope()
    try:
        version = int(parts[4])
    except ValueError as exc:
        raise PiiMalformedEnvelope() from exc
    if version < 1 or str(version) != parts[4]:
        raise PiiMalformedEnvelope()
    nonce, ciphertext = _decode(parts[5]), _decode(parts[6])
    if len(nonce) != 12 or len(ciphertext) < 16:
        raise PiiMalformedEnvelope()
    return version, nonce, ciphertext


def envelope_version(envelope):
    return parse_envelope(envelope)[0]


def encrypt(plaintext, dek, *, key_version, user_id, table, pk, field):
    if not isinstance(plaintext, bytes) or not isinstance(key_version, int) or key_version < 1:
        raise PiiUnavailable()
    try:
        nonce = secrets.token_bytes(12)
        ciphertext = AESGCM(require_dek(dek)).encrypt(nonce, plaintext, aad(user_id, table, pk, field))
    except PiiUnavailable:
        raise
    except Exception as exc:
        raise PiiUnavailable() from exc
    return f"{PREFIX}{key_version}:{_encode(nonce)}:{_encode(ciphertext)}"


def decrypt(envelope, dek, *, user_id, table, pk, field):
    _, nonce, ciphertext = parse_envelope(envelope)
    try:
        return AESGCM(require_dek(dek)).decrypt(nonce, ciphertext, aad(user_id, table, pk, field))
    except InvalidTag as exc:
        raise PiiAuthenticationFailed() from exc
    except PiiUnavailable:
        raise
    except Exception as exc:
        raise PiiUnavailable() from exc

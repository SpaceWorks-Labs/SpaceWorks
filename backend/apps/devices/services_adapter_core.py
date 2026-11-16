"""Shared helpers of the Device Adapter API: typed errors, schema validation, audit and credential digests."""
import hashlib
import hmac
import re

from django.conf import settings
from django.utils.translation import gettext
from rest_framework.exceptions import APIException

from apps.audit import services as audit
from apps.devices.adapters.schema import errors as schema_errors

MAX_ITEMS = 50


class AdapterError(APIException):
    """A typed refusal: ``{"detail", "code"}`` with a stable, documented code (docs/device-adapters/errors.md)."""

    status_code = 400
    default_code = "adapter_error"

    def __init__(self, code, detail, *, status_code=None, **extra):
        super().__init__({"detail": detail, "code": code, **extra}, code)
        self.default_code = code
        if status_code:
            self.status_code = status_code


def check(schema, value, *, label="body"):
    """Validate against the SAME schema dict that is published under docs/device-adapters/schemas."""
    problems = schema_errors(schema, value)
    if problems:
        raise AdapterError("invalid_payload", gettext("The %(what)s does not match the contract.") % {"what": label},
                           errors=problems[:10])
    return value


def audit_adapter(makerspace, device, action, *, target=None, meta=None):
    """One audit row per adapter-originated mutation; a device is never the actor (``actor=None``)."""
    audit.record(None, action, makerspace=makerspace, target=target or device,
                 meta={"device_id": str(device.pk), "device_name": device.name, **(meta or {})})


def credential_digest(makerspace_id, kind, secret, *, user_id=None):
    """HMAC-SHA256 of an NFC id or PIN, keyed by the deployment secret and scoped to the tenant (and user for a PIN).

    A raw tag id or PIN is never stored or logged; a database leak alone cannot be replayed without the secret key.
    """
    scope = f"adapter-credential:{kind}:{makerspace_id}:{user_id or ''}".encode("utf-8")
    key = hashlib.sha256(settings.SECRET_KEY.encode("utf-8") + scope).digest()
    return hmac.new(key, str(secret).strip().encode("utf-8"), hashlib.sha256).hexdigest()


# --- server signing key (offline access cache, signed time) -------------------------------------------------------
# One Ed25519 keypair per key VERSION, derived with HKDF-SHA256 from the deployment SECRET_KEY. The adapter gets only the
# PUBLIC keys (hello ``cache_keys``) and verifies; nothing symmetric ever leaves the server. Rotation: raise
# ``ADAPTER_CACHE_KEY_VERSION`` (default 1); the server signs with the current version and hello still lists the previous
# version as ``previous`` for ``ADAPTER_CACHE_KEY_GRACE_DAYS`` (default 7) after ``ADAPTER_CACHE_KEY_ROTATED_AT`` (epoch),
# so caches already issued stay verifiable until they expire. Rotating ``SECRET_KEY`` itself replaces these keys at once
# (adapters must re-run hello) and also invalidates every stored NFC/PIN digest and every derived webhook secret.
def _private_key(version):
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.hkdf import HKDF
    return HKDF(algorithm=hashes.SHA256(), length=32, salt=b"spaceworks-adapter-cache-v1",
                info=f"ed25519:{version}".encode("ascii")).derive(settings.SECRET_KEY.encode("utf-8"))


def current_kid():
    return max(1, int(getattr(settings, "ADAPTER_CACHE_KEY_VERSION", 1)))


def _public_key(version):
    from apps.ed25519 import encode_key
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    raw = Ed25519PrivateKey.from_private_bytes(_private_key(version)).public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    return encode_key(raw)


def cache_keys(now=None):
    """Public keys an adapter should trust: the current one, plus the previous during the rotation grace period."""
    import time
    kid = current_kid()
    keys = [{"kid": kid, "public_key": _public_key(kid), "status": "current"}]
    rotated = int(getattr(settings, "ADAPTER_CACHE_KEY_ROTATED_AT", 0) or 0)
    grace = int(getattr(settings, "ADAPTER_CACHE_KEY_GRACE_DAYS", 7)) * 86400
    if kid > 1 and (not rotated or (now or time.time()) - rotated < grace):
        keys.append({"kid": kid - 1, "public_key": _public_key(kid - 1), "status": "previous"})
    return keys


# Every signed document names its purpose and frames its fields (lead 10): the offline cache and the signed time share
# one key, so a signature over one can never be read as the other, and no field can borrow bytes from its neighbour.
# Message = ASCII domain + NUL, then per field a 4-byte big-endian length and the UTF-8 bytes (docs: media-and-data.md).
CACHE_DOMAIN = "spaceworks-adapter-offline-cache-v1"
TIME_DOMAIN = "spaceworks-adapter-time-v1"
# The signed-time nonce is chosen by the adapter (fresh random per call) and is REQUIRED in this canonical form.
TIME_NONCE = re.compile(r"^[A-Za-z0-9_-]{16,64}$")


def framed(domain, *fields):
    out = bytearray(domain.encode("ascii") + b"\x00")
    for field in fields:
        raw = str(field).encode("utf-8")
        out += len(raw).to_bytes(4, "big") + raw
    return bytes(out)


def sign(message):
    """(kid, hex Ed25519 signature) of the framed ``message`` bytes with the CURRENT key."""
    from apps.ed25519 import sign_bytes
    if not isinstance(message, bytes):
        raise TypeError("sign() takes framed bytes; build them with framed(domain, ...).")
    kid = current_kid()
    return kid, sign_bytes(message, _private_key(kid)).hex()

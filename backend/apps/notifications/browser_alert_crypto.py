"""W3C Web Push message encryption (RFC 8291, aes128gcm) and VAPID (RFC 8292).

Built on `cryptography` alone (already a dependency), so no new package is pulled in.
The payload is encrypted to the browser's P-256 key with its auth secret; the push
service only ever sees ciphertext. VAPID signs a short-lived ES256 JWT whose audience is
the push service origin, proving the sender without any shared secret.
"""

import base64
import json
import os
import struct
import time
from urllib.parse import urlsplit

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

RECORD_SIZE = 4096
POINT = (serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)


def b64u(raw):
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def unb64u(text):
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def _hkdf(length, salt, info, key):
    return HKDF(algorithm=hashes.SHA256(), length=length, salt=salt, info=info).derive(key)


def encrypt(payload, p256dh, auth_secret, *, salt=None, sender_key=None):
    """Return the aes128gcm body for one record (payload must fit one 4 KiB record)."""
    browser_public = unb64u(p256dh)
    auth = unb64u(auth_secret)
    if len(browser_public) != 65 or len(auth) != 16 or len(payload) > RECORD_SIZE - 103:
        raise ValueError("Invalid browser subscription keys or payload size")
    browser_key = ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), browser_public)
    sender_key = sender_key or ec.generate_private_key(ec.SECP256R1())
    sender_public = sender_key.public_key().public_bytes(*POINT)
    shared = sender_key.exchange(ec.ECDH(), browser_key)
    ikm = _hkdf(32, auth, b"WebPush: info\x00" + browser_public + sender_public, shared)
    salt = salt or os.urandom(16)
    cek = _hkdf(16, salt, b"Content-Encoding: aes128gcm\x00", ikm)
    nonce = _hkdf(12, salt, b"Content-Encoding: nonce\x00", ikm)
    ciphertext = AESGCM(cek).encrypt(nonce, payload + b"\x02", None)
    return salt + struct.pack("!IB", RECORD_SIZE, len(sender_public)) + sender_public + ciphertext


def private_key(raw):
    scalar = int.from_bytes(unb64u(raw), "big")
    return ec.derive_private_key(scalar, ec.SECP256R1())


def public_key(raw):
    return b64u(private_key(raw).public_key().public_bytes(*POINT))


def vapid_headers(endpoint, raw_private_key, subject, *, ttl=3600, now=None):
    parts = urlsplit(endpoint)
    audience = f"{parts.scheme}://{parts.netloc}"
    header = b64u(json.dumps({"typ": "JWT", "alg": "ES256"}, separators=(",", ":")).encode())
    claims = b64u(json.dumps({"aud": audience, "exp": int(now or time.time()) + 12 * 3600, "sub": subject},
                             separators=(",", ":")).encode())
    key = private_key(raw_private_key)
    r, s = decode_dss_signature(key.sign(f"{header}.{claims}".encode(), ec.ECDSA(hashes.SHA256())))
    token = f"{header}.{claims}.{b64u(r.to_bytes(32, 'big') + s.to_bytes(32, 'big'))}"
    return {"Authorization": f"vapid t={token}, k={public_key(raw_private_key)}", "TTL": str(ttl),
            "Content-Encoding": "aes128gcm", "Content-Type": "application/octet-stream", "Urgency": "normal"}

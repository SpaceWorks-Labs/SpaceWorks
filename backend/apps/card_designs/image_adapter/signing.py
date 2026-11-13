"""HMAC-SHA256 request signing for the image adapter contract (v1).

Signed string (UTF-8, LF separated):

    SW-IMAGE-ADAPTER-V1 LF METHOD LF PATH LF TIMESTAMP LF NONCE LF BODY_SHA256_HEX

`PATH` is the URL path exactly as sent (no scheme, host or query). The header `X-SW-Signature` carries
`v1=<hex hmac>`. `verify` is what a provider runs; it is kept here, dependency-free, so tests and the docs'
reference snippet share the one implementation.
"""
import hashlib
import hmac
import secrets
import time

from .contract import CANONICAL_PREFIX, SIGNATURE_SCHEME, TIMESTAMP_SKEW_SECONDS


def body_digest(body: bytes) -> str:
    return hashlib.sha256(body or b"").hexdigest()


def canonical(method, path, timestamp, nonce, digest) -> bytes:
    return "\n".join((CANONICAL_PREFIX, method.upper(), path, str(timestamp), nonce, digest)).encode()


def sign(secret, method, path, body: bytes, *, timestamp=None, nonce=None):
    """-> dict of the four signing headers (the client adds the version header)."""
    timestamp = int(time.time()) if timestamp is None else int(timestamp)
    nonce = nonce or secrets.token_hex(16)
    digest = body_digest(body)
    mac = hmac.new(secret.encode(), canonical(method, path, timestamp, nonce, digest), hashlib.sha256).hexdigest()
    return {"X-SW-Timestamp": str(timestamp), "X-SW-Nonce": nonce, "X-SW-Body-SHA256": digest,
            "X-SW-Signature": f"{SIGNATURE_SCHEME}={mac}"}


def verify(secret, method, path, body: bytes, headers, *, now=None, seen_nonce=None):
    """-> None when valid, else the provider error code to answer with.

    `headers` is any mapping with the X-SW-* names; `seen_nonce(nonce) -> bool` is the provider's replay store
    (it must remember a nonce for NONCE_WINDOW_SECONDS and return True when it has seen it already).
    """
    now = time.time() if now is None else now

    def get(name):
        return headers.get(name) or headers.get(name.lower()) or ""

    try:
        timestamp = int(get("X-SW-Timestamp"))
    except ValueError:
        return "invalid_signature"
    nonce, digest, given = get("X-SW-Nonce"), get("X-SW-Body-SHA256"), get("X-SW-Signature")
    if not nonce or not given.startswith(SIGNATURE_SCHEME + "="):
        return "invalid_signature"
    if not hmac.compare_digest(digest, body_digest(body)):
        return "invalid_signature"
    expected = hmac.new(secret.encode(), canonical(method, path, timestamp, nonce, digest), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(given[len(SIGNATURE_SCHEME) + 1:], expected):
        return "invalid_signature"
    if abs(now - timestamp) > TIMESTAMP_SKEW_SECONDS:
        return "stale_timestamp"
    if seen_nonce is not None and seen_nonce(nonce):
        return "replayed_nonce"
    return None

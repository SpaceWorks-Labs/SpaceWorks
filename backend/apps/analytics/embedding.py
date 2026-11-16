"""Metabase signed (static) embedding: a server-side HS256 token with a short expiry.

The embed secret never leaves the server; the browser only receives the signed URL. A
token names exactly one dashboard and no parameters, and it expires after
``EMBED_TTL_SECONDS`` (Metabase refuses it after that).
"""

import base64
import hashlib
import hmac
import json
import time
from datetime import UTC, datetime
from urllib.parse import urlsplit

EMBED_TTL_SECONDS = 600


class EmbedUrlInvalid(ValueError):
    pass


def _b64(raw):
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def sign(secret, payload):
    header = _b64(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode())
    body = _b64(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode())
    signature = hmac.new(secret.encode("utf-8"), f"{header}.{body}".encode("ascii"), hashlib.sha256).digest()
    return f"{header}.{body}.{_b64(signature)}"


def normalize_site_url(value):
    """``http(s)://host[:port][/path]`` with no credentials, query or fragment; no trailing slash."""
    value = (value or "").strip()
    if not value:
        return ""
    parts = urlsplit(value)
    if parts.scheme not in {"http", "https"} or not parts.hostname:
        raise EmbedUrlInvalid("The Metabase URL must start with http:// or https://.")
    if parts.username or parts.password or parts.query or parts.fragment:
        raise EmbedUrlInvalid("The Metabase URL cannot carry credentials, a query or a fragment.")
    if len(value) > 300:
        raise EmbedUrlInvalid("The Metabase URL is too long.")
    return value.rstrip("/")


def dashboard_url(site_url, secret, dashboard_id, *, now=None, ttl=EMBED_TTL_SECONDS):
    """(signed embed URL, expiry as an aware datetime)."""
    issued = int(now if now is not None else time.time())
    expires = issued + int(ttl)
    token = sign(secret, {"resource": {"dashboard": int(dashboard_id)}, "params": {}, "exp": expires})
    url = f"{normalize_site_url(site_url)}/embed/dashboard/{token}#bordered=true&titled=true"
    return url, datetime.fromtimestamp(expires, tz=UTC)

---
title: Image Adapter API: authentication
group: Reference
order: 63
summary: How a provider verifies that a request really comes from SpaceWorks: HMAC-SHA256 over method, path, time, nonce and body digest.
---

# Authentication

Every request, including `GET /v1/health`, is signed with a **shared secret** (at least 16 characters) that you set
in SpaceWorks and in your provider. There is no other credential, so serve the provider over **https** wherever it
crosses a network you do not control.

## Headers

| Header | Value |
|---|---|
| `X-SW-Adapter-Version` | `1` |
| `X-SW-Timestamp` | Unix time in seconds when SpaceWorks signed the request |
| `X-SW-Nonce` | 32 hex characters, unique per request |
| `X-SW-Body-SHA256` | lowercase hex SHA-256 of the **exact request body bytes** (of an empty body for `GET`) |
| `X-SW-Signature` | `v1=` followed by the lowercase hex HMAC |

## The signed string

Six fields, joined by a single line feed (`\n`, no trailing newline):

```
SW-IMAGE-ADAPTER-V1
POST
/v1/remove-background
1731340800
3f9c1a0b5d7e42a8b6c0d1e2f3a49586
9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08
```

That is: the fixed prefix, the HTTP method (upper case), the URL **path as sent** (no scheme, host or query; include
any prefix from the provider address), the timestamp, the nonce and the body digest. The signature is
`HMAC-SHA256(secret, that string)`, written as lowercase hex.

## What a provider must check

Run these in order and answer with the typed error, never anything else:

1. The headers are present and `X-SW-Signature` starts with `v1=`, else `401 invalid_signature`.
2. `SHA-256(body)` equals `X-SW-Body-SHA256`, else `401 invalid_signature`.
3. The recomputed HMAC equals the signature (use a **constant-time** comparison), else `401 invalid_signature`.
4. `|now - timestamp| <= 300` seconds, else `401 stale_timestamp`.
5. The nonce has not been seen in the last 600 seconds, else `409 replayed_nonce`; then remember it.

Check the digest and HMAC **before** parsing the multipart body, and limit the body read to 8 MB plus overhead so an
unauthenticated caller cannot make you buffer more.

## Reference verifier (Python, no dependencies)

This is the same function SpaceWorks uses in its tests (`backend/apps/card_designs/image_adapter/signing.py`):

```python
import hashlib, hmac, time

PREFIX = "SW-IMAGE-ADAPTER-V1"

def verify(secret, method, path, body, headers, seen_nonce, now=None):
    """Return None when valid, else the error code to answer with."""
    now = time.time() if now is None else now
    get = lambda name: headers.get(name) or headers.get(name.lower()) or ""
    try:
        timestamp = int(get("X-SW-Timestamp"))
    except ValueError:
        return "invalid_signature"
    nonce, digest, given = get("X-SW-Nonce"), get("X-SW-Body-SHA256"), get("X-SW-Signature")
    if not nonce or not given.startswith("v1="):
        return "invalid_signature"
    if not hmac.compare_digest(digest, hashlib.sha256(body).hexdigest()):
        return "invalid_signature"
    text = "\n".join((PREFIX, method.upper(), path, str(timestamp), nonce, digest)).encode()
    expected = hmac.new(secret.encode(), text, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(given[3:], expected):
        return "invalid_signature"
    if abs(now - timestamp) > 300:
        return "stale_timestamp"
    if seen_nonce(nonce):              # your replay store: True if already seen; remember it for 600 s
        return "replayed_nonce"
    return None
```

## Rotating the secret

Change it in the provider first, accepting both the old and the new secret for a few minutes if you can, then
replace it in SpaceWorks (**Replace service**). SpaceWorks shows only a short fingerprint of the stored secret and
audits every save, rotation and removal.

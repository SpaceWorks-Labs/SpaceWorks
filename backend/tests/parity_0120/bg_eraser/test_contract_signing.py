"""The v1 contract's HMAC signing and the provider-side verification (the check any provider must run)."""
from apps.card_designs.image_adapter import contract, signing

SECRET = "a-shared-secret-of-sufficient-length"
BODY = b"--boundary\r\nmultipart body bytes\r\n--boundary--"


def _headers(**override):
    headers = signing.sign(SECRET, "POST", "/v1/remove-background", BODY, timestamp=1_700_000_000, nonce="n" * 32)
    headers.update(override)
    return headers


def test_sign_is_deterministic_and_covers_method_path_time_nonce_and_body():
    base = _headers()
    assert base == _headers()
    assert base["X-SW-Signature"].startswith("v1=")
    assert base["X-SW-Body-SHA256"] == signing.body_digest(BODY)
    other = signing.sign(SECRET, "POST", "/v1/other", BODY, timestamp=1_700_000_000, nonce="n" * 32)
    assert other["X-SW-Signature"] != base["X-SW-Signature"]
    assert signing.sign(SECRET, "GET", "/v1/remove-background", BODY, timestamp=1_700_000_000,
                        nonce="n" * 32)["X-SW-Signature"] != base["X-SW-Signature"]


def test_a_valid_request_verifies():
    assert signing.verify(SECRET, "POST", "/v1/remove-background", BODY, _headers(), now=1_700_000_010) is None


def test_wrong_secret_body_path_or_method_is_invalid_signature():
    headers = _headers()
    now = 1_700_000_010
    assert signing.verify("x" * 20, "POST", "/v1/remove-background", BODY, headers, now=now) == "invalid_signature"
    assert signing.verify(SECRET, "POST", "/v1/remove-background", BODY + b"!", headers, now=now) == "invalid_signature"
    assert signing.verify(SECRET, "POST", "/v1/health", BODY, headers, now=now) == "invalid_signature"
    assert signing.verify(SECRET, "GET", "/v1/remove-background", BODY, headers, now=now) == "invalid_signature"


def test_malformed_headers_are_invalid_signature():
    now = 1_700_000_010
    assert signing.verify(SECRET, "POST", "/v1/remove-background", BODY, _headers(**{"X-SW-Timestamp": "soon"}),
                          now=now) == "invalid_signature"
    assert signing.verify(SECRET, "POST", "/v1/remove-background", BODY, _headers(**{"X-SW-Signature": "nope"}),
                          now=now) == "invalid_signature"
    assert signing.verify(SECRET, "POST", "/v1/remove-background", BODY, {}, now=now) == "invalid_signature"


def test_stale_timestamps_are_refused_in_both_directions():
    headers = _headers()
    far = contract.TIMESTAMP_SKEW_SECONDS + 5
    assert signing.verify(SECRET, "POST", "/v1/remove-background", BODY, headers, now=1_700_000_000 + far) == "stale_timestamp"
    assert signing.verify(SECRET, "POST", "/v1/remove-background", BODY, headers, now=1_700_000_000 - far) == "stale_timestamp"


def test_a_replayed_nonce_is_refused():
    seen = set()

    def seen_nonce(nonce):
        known = nonce in seen
        seen.add(nonce)
        return known

    args = (SECRET, "POST", "/v1/remove-background", BODY, _headers())
    assert signing.verify(*args, now=1_700_000_001, seen_nonce=seen_nonce) is None
    assert signing.verify(*args, now=1_700_000_002, seen_nonce=seen_nonce) == "replayed_nonce"


def test_header_lookup_is_case_insensitive_for_lowercase_servers():
    lowered = {key.lower(): value for key, value in _headers().items()}
    assert signing.verify(SECRET, "POST", "/v1/remove-background", BODY, lowered, now=1_700_000_010) is None


def test_the_capability_registry_names_the_v1_path():
    capability = contract.CAPABILITIES["image.remove_background"]
    assert capability.path == "/v1/remove-background" and contract.VERSION == "1"
    assert contract.PROVIDER_ERRORS["invalid_signature"] == 401
    assert contract.RETRYABLE <= contract.ALL_ERROR_CODES

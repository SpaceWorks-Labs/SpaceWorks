"""The v1 wire contract and its capability registry. Constants only; no I/O.

Anything a provider author needs is here and mirrored in `docs/image-adapters/`. Changing a value below is a
contract change: bump `VERSION`, never edit v1 in place.
"""
from dataclasses import dataclass

VERSION = "1"
SIGNATURE_SCHEME = "v1"
CANONICAL_PREFIX = "SW-IMAGE-ADAPTER-V1"

HEADER_VERSION = "X-SW-Adapter-Version"
HEADER_TIMESTAMP = "X-SW-Timestamp"
HEADER_NONCE = "X-SW-Nonce"
HEADER_BODY_SHA256 = "X-SW-Body-SHA256"
HEADER_SIGNATURE = "X-SW-Signature"

# A provider must reject a request whose timestamp is further than this from its own clock and must refuse a
# nonce it has already seen inside the window (replay protection).
TIMESTAMP_SKEW_SECONDS = 300
NONCE_WINDOW_SECONDS = 600

# Inputs SpaceWorks may send (a provider MUST accept all three) and the bounds every provider must honour.
INPUT_TYPES = ("image/png", "image/jpeg", "image/webp")
MAX_INPUT_BYTES = 8 * 1024 * 1024
MAX_INPUT_EDGE = 4096
MAX_OUTPUT_BYTES = 16 * 1024 * 1024
MAX_MASK_BYTES = 8 * 1024 * 1024

CONNECT_TIMEOUT = 5
READ_TIMEOUT = 60

# Typed error codes a provider answers with: `{"error": {"code", "message", "retryable"}}` and the HTTP status.
PROVIDER_ERRORS = {
    "invalid_signature": 401, "stale_timestamp": 401, "replayed_nonce": 409, "unsupported_media_type": 415,
    "payload_too_large": 413, "dimensions_too_large": 422, "unreadable_image": 422, "no_subject_found": 422,
    "rate_limited": 429, "unavailable": 503, "internal_error": 500,
}
# Codes worth retrying with backoff; the rest are final for that photo.
RETRYABLE = frozenset({"rate_limited", "unavailable", "internal_error", "provider_unreachable", "provider_timeout"})
# Codes SpaceWorks itself raises about a provider or its answer.
CLIENT_ERRORS = frozenset({
    "not_configured", "provider_unreachable", "provider_timeout", "invalid_response", "response_not_png",
    "response_no_alpha", "response_empty", "response_too_large", "response_shape_mismatch", "mask_unreachable",
    "url_not_allowed", "input_not_allowed", "photo_missing",
})
ALL_ERROR_CODES = frozenset(PROVIDER_ERRORS) | CLIENT_ERRORS


@dataclass(frozen=True)
class Capability:
    key: str
    path: str
    summary: str
    since: str = "1"
    methods: tuple = ("POST",)


CAPABILITIES = {
    "image.remove_background": Capability(
        "image.remove_background", "/v1/remove-background",
        "Return the subject of the photo on a transparent background (PNG with alpha), or a mask URL."),
}
HEALTH_PATH = "/v1/health"

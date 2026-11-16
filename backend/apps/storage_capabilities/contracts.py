"""Immutable, credential-independent identity and capability values."""

from dataclasses import asdict, dataclass
import hashlib
import json
from urllib.parse import urlsplit, urlunsplit

from botocore.exceptions import BotoCoreError


class CapabilityError(BotoCoreError):
    """Safe, typed refusal suitable for readiness and domain error adapters."""

    fmt = "{code}"

    def __init__(self, code):
        self.code = code
        super().__init__(code=code)


def fingerprint(value):
    return hashlib.sha256(json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
    ).encode("ascii")).hexdigest()


def normalize_endpoint(endpoint):
    try:
        parsed = urlsplit(endpoint)
        port = parsed.port
        if (
            parsed.scheme not in {"http", "https"} or not parsed.hostname
            or parsed.username is not None or parsed.password is not None
            or parsed.query or parsed.fragment
        ):
            raise ValueError
        host = parsed.hostname.lower()
        if ":" in host:
            host = f"[{host}]"
        if port is not None and (parsed.scheme, port) not in {("http", 80), ("https", 443)}:
            host = f"{host}:{port}"
        return urlunsplit((parsed.scheme, host, parsed.path.rstrip("/"), "", ""))
    except (ValueError, TypeError, AttributeError):
        raise CapabilityError("storage_endpoint_invalid") from None


@dataclass(frozen=True)
class StorageIdentity:
    endpoint: str
    region: str
    bucket: str

    @classmethod
    def build(cls, endpoint, region, bucket):
        if not isinstance(region, str) or not region or len(region) > 100:
            raise CapabilityError("storage_region_invalid")
        if (
            not isinstance(bucket, str) or not bucket or len(bucket) > 255
            or bucket != bucket.strip() or any(c in bucket for c in "/\\\x00")
        ):
            raise CapabilityError("storage_bucket_invalid")
        return cls(normalize_endpoint(endpoint), region, bucket)

    @property
    def fingerprint(self):
        return fingerprint(asdict(self))


@dataclass(frozen=True)
class StorageCapabilities:
    identity: StorageIdentity
    generation: int
    presign_methods: frozenset[str]
    versioning: str
    list_delete_versions: bool | None
    conditional_create: bool | None
    copy: bool | None
    multipart: bool | None
    object_lock: bool | None
    cors_management: bool | None
    staging_policy: str
    public_delivery: str
    max_object_bytes: int | None = None

    @property
    def fingerprint(self):
        values = asdict(self)
        values["presign_methods"] = sorted(self.presign_methods)
        return fingerprint(values)

    def presign_method(self, requested):
        if not isinstance(requested, str) or requested not in {"auto", "put", "post"}:
            raise CapabilityError("storage_presign_method_invalid")
        if requested == "auto":
            requested = "post" if "post" in self.presign_methods else "put"
        if requested not in self.presign_methods:
            raise CapabilityError("storage_presign_method_unsupported")
        return requested

    def validate_upload_limit(self, maximum):
        if type(maximum) is not int or maximum < 1:
            raise CapabilityError("storage_upload_limit_invalid")
        if self.max_object_bytes is not None and maximum > self.max_object_bytes:
            raise CapabilityError("storage_provider_object_limit_exceeded")

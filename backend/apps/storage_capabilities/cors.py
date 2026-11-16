"""Exact-origin CORS data for explicit provisioning/manual setup, never startup."""

from urllib.parse import urlsplit

from .contracts import CapabilityError


def cors_rules(frontend_origins, presign_methods):
    if (
        not isinstance(frontend_origins, (list, tuple)) or not 1 <= len(frontend_origins) <= 100
        or not isinstance(presign_methods, (list, tuple, set, frozenset)) or not presign_methods
        or any(not isinstance(method, str) or method not in {"put", "post"} for method in presign_methods)
    ):
        raise CapabilityError("storage_cors_configuration_invalid")
    origins = []
    for origin in frontend_origins:
        try:
            parsed = urlsplit(origin)
            if (
                parsed.scheme not in {"http", "https"} or not parsed.hostname
                or parsed.username or parsed.password or parsed.path or parsed.query
                or parsed.fragment or "*" in origin
            ):
                raise ValueError
            parsed.port
        except (TypeError, ValueError, AttributeError):
            raise CapabilityError("storage_cors_origin_invalid") from None
        origins.append(origin)
    return {"CORSRules": [{
        "AllowedOrigins": sorted(set(origins)),
        "AllowedMethods": ["GET", "HEAD", "PUT"] + (["POST"] if "post" in presign_methods else []),
        "AllowedHeaders": ["Content-Type", "If-Match", "If-None-Match", "x-amz-checksum-sha256",
                           "x-amz-checksum-crc32", "x-amz-sdk-checksum-algorithm"],
        "ExposeHeaders": ["ETag", "x-amz-version-id", "x-amz-checksum-sha256", "x-amz-checksum-crc32"],
        "MaxAgeSeconds": 3600,
    }]}

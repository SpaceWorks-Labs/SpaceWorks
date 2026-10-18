"""Shared upload policy and private public-image staging locators."""

from dataclasses import dataclass
from urllib.parse import urlsplit

from .contracts import CapabilityError
from .runtime import capabilities_for
from .verification import verified_state


@dataclass(frozen=True)
class ObjectLocator:
    bucket: str
    key: str


def public_image_staging(final_key, *, private_bucket):
    if not isinstance(final_key, str) or not final_key or final_key.startswith("/") or "\x00" in final_key:
        raise CapabilityError("storage_object_key_invalid")
    return ObjectLocator(private_bucket, f"staging/public-images/{final_key}")


def public_image_staging_candidates(final_key, *, private_bucket, public_bucket):
    """New private locator first; retain old public staging until it is drained."""
    return (
        public_image_staging(final_key, private_bucket=private_bucket),
        ObjectLocator(public_bucket, f"staging/{final_key}"),
    )


def upload_method(client, *, bucket, requested):
    contract = capabilities_for(client, bucket, required=True, role="private")
    return _upload_method(contract, requested)


def _upload_method(contract, requested):
    if contract is not None:
        method = contract.presign_method(requested)
        if method not in verified_state(contract).facts.get("presign_methods", ()):
            raise CapabilityError("storage_presign_method_unproven")
        return method
    if requested not in {"put", "post"}:
        raise CapabilityError("storage_auto_requires_capability_contract")
    return requested


def presign_upload(signing_client, *, backend_client, bucket, key, content_type,
                   max_bytes, ttl, requested):
    """Sign the reachable API host directly, without rewriting the signed URL."""
    if type(ttl) is not int or not 1 <= ttl <= 604800:
        raise CapabilityError("storage_presign_ttl_invalid")
    if type(max_bytes) is not int or max_bytes < 1:
        raise CapabilityError("storage_upload_limit_invalid")
    if not isinstance(content_type, str) or not content_type or any(c in content_type for c in "\r\n"):
        raise CapabilityError("storage_content_type_invalid")
    host = urlsplit(signing_client.meta.endpoint_url).hostname or ""
    if host == "r2.dev" or host.endswith(".r2.dev"):
        raise CapabilityError("storage_presign_requires_api_endpoint")
    contract = capabilities_for(backend_client, bucket, required=True, role="private")
    if contract is not None:
        contract.validate_upload_limit(max_bytes)
    method = _upload_method(contract, requested)
    from django.conf import settings
    free = getattr(settings, "SPACEWORKS_DEPLOYMENT_PROFILE", "full") == "free"
    if free and requested == "auto" and contract.versioning != "never_versioned":
        method = _upload_method(contract, "put")
    if free and method == "post" and contract.versioning != "never_versioned":
        raise CapabilityError("storage_free_replayable_post_refused")
    if free and method == "put":
        from .runtime import require_capability
        require_capability(backend_client, bucket, "conditional_create", role="private")
        if verified_state(contract).facts.get("put_conditional_presign") is not True:
            raise CapabilityError("storage_put_conditional_presign_unproven")
    if getattr(settings, "SPACEWORKS_DEPLOYMENT_MODE", "host") == "managed":
        from apps.backup.managed.presigns import register_presign
        register_presign(ttl)
    from apps.operations.cloud_quotas.storage import reserve_upload
    reserve_upload(backend_client, bucket=bucket, key=key, max_bytes=max_bytes, ttl=ttl)
    if method == "put":
        params = {"Bucket": bucket, "Key": key, "ContentType": content_type}
        headers = {"Content-Type": content_type}
        if free:
            params["IfNoneMatch"] = "*"
            headers["If-None-Match"] = "*"
        url = signing_client.generate_presigned_url(
            "put_object", Params=params,
            ExpiresIn=ttl,
        )
        return {"url": url, "method": "PUT", "headers": headers}
    return signing_client.generate_presigned_post(
        Bucket=bucket, Key=key, Fields={"Content-Type": content_type},
        Conditions=[{"Content-Type": content_type}, ["content-length-range", 1, max_bytes]],
        ExpiresIn=ttl,
    )

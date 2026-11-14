"""Shared upload policy and private public-image staging locators."""

from contextlib import contextmanager, nullcontext
from contextvars import ContextVar
from dataclasses import dataclass
from urllib.parse import urlsplit

from .contracts import CapabilityError
from .runtime import capabilities_for
from .verification import verified_state

_renewal = ContextVar("storage_upload_renewal", default=None)


@contextmanager
def renewal_authorization(*, bucket, key, max_bytes):
    """Carry a locked domain retry's exact identity into deployment admission."""
    token = _renewal.set((bucket, key, max_bytes))
    try:
        yield
    finally:
        _renewal.reset(token)


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
                   max_bytes, ttl, requested, exact_bytes=None):
    """Sign the reachable API host directly, without rewriting the signed URL."""
    if type(ttl) is not int or not 1 <= ttl <= 604800:
        raise CapabilityError("storage_presign_ttl_invalid")
    if type(max_bytes) is not int or max_bytes < 1:
        raise CapabilityError("storage_upload_limit_invalid")
    admission_maximum = max_bytes
    if requested not in {"put", "post", "auto"}:
        raise CapabilityError("storage_presign_method_invalid")
    if not isinstance(content_type, str) or not content_type or any(c in content_type for c in "\r\n"):
        raise CapabilityError("storage_content_type_invalid")
    host = urlsplit(signing_client.meta.endpoint_url).hostname or ""
    if host == "r2.dev" or host.endswith(".r2.dev"):
        raise CapabilityError("storage_presign_requires_api_endpoint")
    contract = capabilities_for(backend_client, bucket, required=True, role="private")
    if exact_bytes is not None and (type(exact_bytes) is not int or not 1 <= exact_bytes <= max_bytes):
        raise CapabilityError("storage_upload_limit_invalid")
    # PUT can bind an exact declared length, never a range. Undeclared legacy
    # callers must use a provider-enforced POST policy covering the reservation.
    if exact_bytes is None:
        if (contract is None and requested == "put") or (contract is not None and "post" not in contract.presign_methods):
            from django.utils.translation import gettext
            from rest_framework.exceptions import ValidationError
            raise ValidationError({"code": "upload_size_required", "detail": gettext("Declare the upload size in bytes.")})
        requested = "post"
        if contract is not None and contract.max_object_bytes is not None:
            max_bytes = min(max_bytes, contract.max_object_bytes)
    else:
        max_bytes = exact_bytes
    method = _upload_method(contract, requested)
    if contract is not None:
        contract.validate_upload_limit(max_bytes)
    from django.conf import settings
    free = getattr(settings, "SPACEWORKS_DEPLOYMENT_PROFILE", "full") == "free"
    if free and exact_bytes is not None and requested == "auto" and contract.versioning != "never_versioned":
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
    from django.db import transaction
    from apps.operations.cloud_quotas.storage import cover_upload_authorization, reserve_upload
    # Keep deployment admission locked through signing and horizon retention.
    # A failed signer or renewal rolls back both layers in the caller's transaction.
    with transaction.atomic() if free else nullcontext():
        renewal = {"renew": True} if _renewal.get() == (bucket, key, admission_maximum) else {}
        reservation = reserve_upload(backend_client, bucket=bucket, key=key, max_bytes=max_bytes, ttl=ttl, **renewal)
        upload = _sign(signing_client, bucket=bucket, key=key, content_type=content_type,
                       exact_bytes=exact_bytes, max_bytes=max_bytes, ttl=ttl, method=method, free=free)
        if reservation is not None:
            cover_upload_authorization(reservation, ttl=ttl)
        return upload


def _sign(signing_client, *, bucket, key, content_type, exact_bytes, max_bytes, ttl, method, free):
    if method == "put":
        params = {"Bucket": bucket, "Key": key, "ContentType": content_type, "ContentLength": exact_bytes}
        headers = {"Content-Type": content_type, "Content-Length": str(exact_bytes)}
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

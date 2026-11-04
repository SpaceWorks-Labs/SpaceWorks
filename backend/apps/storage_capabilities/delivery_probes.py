"""Bounded private/public delivery and CORS diagnostics for explicit setup.

Run from a surface able to reach the configured browser API/delivery origins.
This supplements, and never replaces, the deployed frontend's browser test.
The caller records the sanitized result in its audited setup/readiness run.
"""

import struct
import uuid
import zlib
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlsplit, urlunsplit
from urllib.request import Request, urlopen

from botocore.exceptions import BotoCoreError, ClientError

from .budget import checkpoint, client_options
from .contracts import CapabilityError, normalize_endpoint
from .cors import cors_rules
from .deletion import delete_exact_key
from .runtime import client_identity


def _png_chunk(kind, data):
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))


PROBE_IMAGE = (b"\x89PNG\r\n\x1a\n"
               + _png_chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 6, 0, 0, 0))
               + _png_chunk(b"IDAT", zlib.compress(b"\x00\x00\x00\x00\x00"))
               + _png_chunk(b"IEND", b""))


def probe_delivery(*, private_client, public_client, signing_client,
                   private_contract, public_contract, public_base_url, frontend_origins):
    if (
        client_identity(private_client, private_contract.identity.bucket) != private_contract.identity
        or client_identity(public_client, public_contract.identity.bucket) != public_contract.identity
        or private_contract.identity == public_contract.identity
    ):
        raise CapabilityError("storage_client_identity_mismatch")
    base = normalize_endpoint(public_base_url)
    cors_rules(frontend_origins, {"put"})
    token = uuid.uuid4().hex
    staged = f"staging/public-images/spaceworks-capability-probes/{token}"
    final = f"spaceworks-capability-probes/{token}"
    payload = PROBE_IMAGE
    private_bucket = private_contract.identity.bucket
    public_bucket = public_contract.identity.bucket
    try:
        checkpoint()
        private_client.put_object(Bucket=private_bucket, Key=staged, Body=payload, ContentType="image/png")
        signed_get = signing_client.generate_presigned_url("get_object", Params={
            "Bucket": private_bucket, "Key": staged,
        }, ExpiresIn=60)
        status, data, _ = _http(Request(signed_get), len(payload) + 1)
        if status != 200 or data != payload:
            raise CapabilityError("storage_signed_download_unproven")
        parsed = urlsplit(signed_get)
        unsigned = urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))
        if _http(Request(unsigned), 0)[0] not in {403, 404}:
            raise CapabilityError("storage_private_staging_publicly_readable")
        checkpoint()
        public_client.put_object(Bucket=public_bucket, Key=final, Body=payload,
                                 ContentType="image/png", IfNoneMatch="*", CacheControl="no-store")
        status, data, _ = _http(Request(base + "/" + quote(final, safe="/")), len(payload) + 1)
        if status != 200 or data != payload:
            raise CapabilityError("storage_public_delivery_unproven")
        for method in sorted(private_contract.presign_methods):
            from apps.backup.managed.presigns import register_presign
            register_presign(60)
            if method == "put":
                from django.conf import settings
                free_put = getattr(settings, "SPACEWORKS_DEPLOYMENT_PROFILE", "full") == "free"
                params = {
                    "Bucket": private_bucket, "Key": staged, "ContentType": "image/png",
                }
                if free_put:
                    params["IfNoneMatch"] = "*"
                upload_url = signing_client.generate_presigned_url("put_object", Params=params, ExpiresIn=60)
            else:
                free_put = False
                upload_url = signing_client.generate_presigned_post(
                    Bucket=private_bucket, Key=staged, ExpiresIn=60,
                )["url"]
            for origin in frontend_origins:
                status, _, headers = _http(Request(upload_url, method="OPTIONS", headers={
                    "Origin": origin, "Access-Control-Request-Method": method.upper(),
                    "Access-Control-Request-Headers": "content-type,if-none-match" if free_put else "content-type",
                }), 0)
                methods = {item.strip() for item in headers.get("Access-Control-Allow-Methods", "").split(",")}
                if status not in {200, 204} or headers.get("Access-Control-Allow-Origin") != origin or method.upper() not in methods:
                    raise CapabilityError("storage_browser_cors_unproven")
                allowed = {item.strip().lower() for item in headers.get("Access-Control-Allow-Headers", "").split(",")}
                if free_put and "*" not in allowed and not {"content-type", "if-none-match"} <= allowed:
                    raise CapabilityError("storage_conditional_upload_cors_unproven")
    except CapabilityError:
        raise
    except (BotoCoreError, ClientError, OSError, KeyError):
        raise CapabilityError("storage_delivery_probe_unknown") from None
    finally:
        failed = False
        for client, contract, key in ((private_client, private_contract, staged),
                                      (public_client, public_contract, final)):
            try:
                delete_exact_key(client, bucket=contract.identity.bucket, key=key,
                                 never_versioned=contract.versioning == "never_versioned")
            except (BotoCoreError, ClientError):
                failed = True
        if failed:
            raise CapabilityError("storage_probe_cleanup_failed") from None
    return {"private_staging": "denied", "signed_download": "verified",
            "public_delivery": "verified", "cors_origins_verified": sorted(set(frontend_origins))}


def _http(request, limit):
    checkpoint()
    try:
        with urlopen(request, timeout=client_options().get("read_timeout", 10)) as response:
            return response.status, response.read(limit) if limit else b"", response.headers
    except HTTPError as exc:
        code, headers = exc.code, exc.headers
        exc.close()
        return code, b"", headers
    except (URLError, OSError, ValueError):
        raise CapabilityError("storage_delivery_probe_unknown") from None

"""Actual signed upload qualification; SDK presign generation proves no policy."""

import uuid
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from botocore.exceptions import BotoCoreError, ClientError

from .budget import checkpoint, client_options
from .contracts import CapabilityError
from .deletion import delete_exact_key


def probe_upload_methods(client, contract):
    """Small scoped objects only; no bucket creation or policy configuration.

    This tests the backend-reachable API. Browser CORS and the independently
    configured browser signing endpoint still require the deployment harness.
    Signed URLs and POST fields are never returned, persisted or logged.
    """
    bucket = contract.identity.bucket
    keys = []
    facts = {"presign_methods": []}
    try:
        for method in sorted(contract.presign_methods):
            key = f"spaceworks-capability-probes/{uuid.uuid4().hex}/{method}"
            keys.append(key)
            checkpoint()
            from apps.backup.managed.presigns import register_presign
            register_presign(60)
            if method == "post":
                signed = client.generate_presigned_post(
                    Bucket=bucket, Key=key, Fields={"Content-Type": "image/png"},
                    Conditions=[{"Content-Type": "image/png"}, ["content-length-range", 1, 16]],
                    ExpiresIn=60,
                )
                if _post(signed, b"valid", "image/png") not in {200, 201, 204}:
                    raise CapabilityError("storage_post_upload_unproven")
                _assert_content(client, bucket, key, b"valid")
                if _post(signed, b"x" * 17, "image/png") not in {400, 403}:
                    raise CapabilityError("storage_post_size_policy_unproven")
                if _post(signed, b"valid", "application/pdf") not in {400, 403}:
                    raise CapabilityError("storage_post_mime_policy_unproven")
                _assert_content(client, bucket, key, b"valid")
                facts["post_size_policy"] = True
            else:
                from django.conf import settings
                free = getattr(settings, "SPACEWORKS_DEPLOYMENT_PROFILE", "full") == "free"
                params = {
                    "Bucket": bucket, "Key": key, "ContentType": "image/png",
                }
                headers = {"Content-Type": "image/png"}
                if free:
                    if contract.conditional_create is not True:
                        raise CapabilityError("storage_free_conditional_create_required")
                    params["IfNoneMatch"], headers["If-None-Match"] = "*", "*"
                url = client.generate_presigned_url("put_object", Params=params, ExpiresIn=60)
                if _request(Request(url, data=b"valid", method="PUT", headers=headers)) not in {200, 201, 204}:
                    raise CapabilityError("storage_put_upload_unproven")
                if free:
                    if _request(Request(url, data=b"replay", method="PUT", headers=headers)) not in {409, 412}:
                        raise CapabilityError("storage_put_presign_replay_accepted")
                    facts["put_conditional_presign"] = True
                if _request(Request(url, data=b"bad", method="PUT", headers={**headers, "Content-Type": "application/pdf"})) not in {400, 403}:
                    raise CapabilityError("storage_put_mime_binding_unproven")
                _assert_content(client, bucket, key, b"valid")
                facts["put_size_validation"] = "finalization"
            facts["presign_methods"].append(method)
    except CapabilityError:
        raise
    except (BotoCoreError, ClientError, OSError, KeyError):
        raise CapabilityError("storage_upload_probe_unknown") from None
    finally:
        failed = False
        for key in keys:
            try:
                delete_exact_key(client, bucket=bucket, key=key,
                                 never_versioned=contract.versioning == "never_versioned")
            except (BotoCoreError, ClientError):
                failed = True
        if failed:
            raise CapabilityError("storage_probe_cleanup_failed") from None
    return facts


def _assert_content(client, bucket, key, expected):
    checkpoint()
    body = client.get_object(Bucket=bucket, Key=key)["Body"]
    try:
        if body.read(len(expected) + 1) != expected:
            raise CapabilityError("storage_upload_readback_mismatch")
    finally:
        body.close()


def _request(request):
    checkpoint()
    timeout = client_options().get("read_timeout", 10)
    try:
        with urlopen(request, timeout=timeout) as response:
            return response.status
    except HTTPError as exc:
        exc.close()
        return exc.code
    except (URLError, OSError, ValueError):
        raise CapabilityError("storage_upload_probe_unknown") from None


def _post(signed, payload, mime):
    boundary = "spaceworks-" + uuid.uuid4().hex
    fields = {**signed["fields"], "Content-Type": mime}
    parts = [
        f'--{boundary}\r\nContent-Disposition: form-data; name="{key}"\r\n\r\n{value}\r\n'.encode()
        for key, value in fields.items()
    ]
    parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="probe.png"\r\nContent-Type: {mime}\r\n\r\n'.encode())
    parts.extend((payload, f"\r\n--{boundary}--\r\n".encode()))
    return _request(Request(signed["url"], data=b"".join(parts), method="POST",
                            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"}))

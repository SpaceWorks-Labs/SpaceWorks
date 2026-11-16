"""Exercise browser presigning and real bytes on unique, disposable storage keys."""
import uuid
from urllib.parse import urlsplit, urlunsplit

from probe_common import ProbeError, request

PAYLOAD = b"Space Works installer storage diagnostic\n"
LOOPBACK = {"localhost", "127.0.0.1", "::1"}


def browser_request(url, *, headers=None, **options):
    """Send a browser-facing request from inside the backend network.

    A loopback public endpoint names the host's published port, which this container
    cannot reach. Connect to the backend-facing endpoint instead and keep the browser
    Host header, which the presigned signature covers.
    """
    from django.conf import settings
    public = urlsplit(getattr(settings, "AWS_S3_PUBLIC_ENDPOINT_URL", "") or "")
    internal = urlsplit(getattr(settings, "AWS_S3_ENDPOINT_URL", "") or "")
    target = urlsplit(url)
    headers = dict(headers or {})
    if (internal.netloc and public.hostname in LOOPBACK and internal.netloc != public.netloc
            and (target.scheme, target.netloc) == (public.scheme, public.netloc)):
        headers["Host"] = target.netloc
        url = urlunsplit(target._replace(scheme=internal.scheme, netloc=internal.netloc))
    return request(url, headers=headers, **options)


def upload(form):
    if form.get("method") == "PUT":
        status, _ = browser_request(form["url"], data=PAYLOAD, headers=form["headers"], method="PUT")
    else:
        boundary = "sw" + uuid.uuid4().hex
        parts = []
        for key, value in form["fields"].items():
            if any(char in key for char in '\r\n"'):
                raise ProbeError("storage_invalid_form")
            parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{key}"\r\n\r\n{value}\r\n'.encode())
        parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="probe.png"\r\nContent-Type: image/png\r\n\r\n'.encode())
        parts.extend([PAYLOAD, f"\r\n--{boundary}--\r\n".encode()])
        status, _ = browser_request(form["url"], data=b"".join(parts),
                                    headers={"Content-Type": "multipart/form-data; boundary=" + boundary})
    if status not in {200, 201, 204}:
        raise ProbeError("storage_presign_upload_failed")


def storage():
    from django.conf import settings
    from apps.evidence import storage as evidence
    from apps.object_storage import delete_all_versions
    key = "installer-probes/" + uuid.uuid4().hex
    staging = evidence.staging_key(key)
    client = evidence._client()
    private, public = settings.AWS_STORAGE_BUCKET_NAME, settings.PUBLIC_IMAGE_BUCKET
    # Exact unique keys only, including all versions on versioned stores.
    try:
        upload(evidence.presigned_upload(key, "image/png"))
        body = client.get_object(Bucket=private, Key=staging)["Body"]
        try:
            if body.read(len(PAYLOAD) + 1) != PAYLOAD:
                raise ProbeError("storage_private_bytes_mismatch")
        finally:
            body.close()
        signed = evidence._public_client().generate_presigned_url(
            "get_object", Params={"Bucket": private, "Key": staging}, ExpiresIn=60)
        parsed = urlsplit(signed)
        status, _ = browser_request(urlunsplit(parsed._replace(query="", fragment="")))
        if status not in {401, 403, 404}:
            raise ProbeError("storage_private_anonymous_access")
        client.put_object(Bucket=public, Key=key, Body=PAYLOAD,
                          ContentType="text/plain", CacheControl="no-store")
        status, body = browser_request(settings.PUBLIC_IMAGE_BASE_URL.rstrip("/") + "/" + key)
        if status != 200 or body != PAYLOAD:
            raise ProbeError("storage_public_bytes_mismatch")
    finally:
        # Attempt both cleanups even when the first one fails.
        failures = []
        for bucket, object_key in ((private, staging), (public, key)):
            try:
                delete_all_versions(client, bucket=bucket, key=object_key)
            except Exception:
                failures.append(True)
        if failures:
            raise ProbeError("storage_probe_cleanup_failed") from None
    return "private_public_presign_bytes_verified"

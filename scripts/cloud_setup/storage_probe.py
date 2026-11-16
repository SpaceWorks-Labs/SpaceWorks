"""Non-provisioning storage checks. No capability is inferred from a denied API."""

from concurrent.futures import ThreadPoolExecutor
import hashlib
from urllib.error import HTTPError
from urllib.parse import quote, urlsplit, urlunsplit
from urllib.request import Request, build_opener
import uuid

from .errors import SetupError
from .private_files import read_json
from .service_probes import NoRedirect


def descriptor_probe(values):
    """Parse the storage lane's strict schema without writing to the provider."""
    import json
    from pathlib import Path
    import tempfile
    from .secret_files import read_config
    from apps.storage_capabilities.configuration import read_configuration
    from apps.storage_capabilities.contracts import StorageIdentity
    path = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", delete=False) as handle:
            path = Path(handle.name)
            json.dump(read_config(values, "STORAGE_CAPABILITIES_FILE"), handle)
        contracts = read_configuration(path)
        for role, name in (("private", "AWS_STORAGE_BUCKET_NAME"), ("public_image", "PUBLIC_IMAGE_BUCKET")):
            contract = contracts[role]
            identity = StorageIdentity.build(values["AWS_S3_ENDPOINT_URL"], values.get("AWS_S3_REGION_NAME", "us-east-1"), values[name])
            if contract.identity != identity or values.get("STORAGE_PRESIGN_METHOD", "put") not in contract.presign_methods:
                raise SetupError("storage_descriptor_identity", "Bind the strict capability descriptor to the actual endpoint, region, bucket and upload method.")
        return {"status": "passed", "schema": 1, "qualification": "required-at-bootstrap"}
    finally:
        if path is not None:
            path.unlink(missing_ok=True)


def storage_probe(values, answers):
    """Use the admitted runtime-only command so setup writes join capture drain."""
    import os
    import subprocess
    import sys
    from .bootstrap import BACKEND
    from .environment import role_environment
    environment = {key: os.environ[key] for key in ("PATH", "HOME", "SYSTEMROOT", "SSL_CERT_FILE", "SSL_CERT_DIR") if key in os.environ}
    environment.update(role_environment(values, "web"), DJANGO_SETTINGS_MODULE="config.settings")
    try:
        subprocess.run([sys.executable, "scripts/cloud_entrypoint.py", "--role", "management",
                        "python", "manage.py", "verify_storage", "--browser-probes"],
                       cwd=BACKEND, env=environment, stdin=subprocess.DEVNULL,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                       timeout=600, check=True)
    except (OSError, subprocess.SubprocessError):
        raise SetupError("storage_qualification_failed", "The native storage/privacy/CORS qualification failed; inspect protected diagnostics and retry with runtime-only credentials.") from None
    return {"status": "passed", "qualification": "native-runtime-and-browser-endpoint"}


def verify_delivery(values, *, check=lambda: None):
    """Called only inside verify_storage's admitted presign writer boundary."""
    import boto3
    from botocore.config import Config
    from apps.storage_capabilities.configuration import read_configuration
    from apps.storage_capabilities.contracts import StorageIdentity

    contracts = read_configuration(values["STORAGE_CAPABILITIES_FILE"])
    options = {"region_name": values.get("AWS_S3_REGION_NAME", "us-east-1"),
               "endpoint_url": values.get("AWS_S3_ENDPOINT_URL") or None,
               "config": Config(connect_timeout=5, read_timeout=5, retries={"max_attempts": 0},
                                signature_version="s3v4", s3={"addressing_style": values.get("AWS_S3_ADDRESSING_STYLE", "auto")})}
    credentials = {"aws_access_key_id": values.get("AWS_ACCESS_KEY_ID"),
                   "aws_secret_access_key": values.get("AWS_SECRET_ACCESS_KEY"),
                   "aws_session_token": values.get("AWS_SESSION_TOKEN")}
    session = boto3.session.Session(**{k: v for k, v in credentials.items() if v})
    client = session.client("s3", **options)
    browser = session.client("s3", **dict(options, endpoint_url=values.get("AWS_S3_PUBLIC_ENDPOINT_URL") or options["endpoint_url"]))
    answers = {"public_origin": values["PUBLIC_APP_BASE_URL"],
               "presign_method": values.get("STORAGE_PRESIGN_METHOD", "put")}
    try:
        results = []
        for role, name in (("private", values["AWS_STORAGE_BUCKET_NAME"]), ("public_image", values["PUBLIC_IMAGE_BUCKET"])):
            check()
            contract = contracts[role]
            if contract.identity != StorageIdentity.build(client.meta.endpoint_url, client.meta.region_name, name):
                raise SetupError("storage_descriptor_identity", "Bind the strict runtime descriptor to the configured bucket endpoint and region.")
            results.append(probe_bucket(client, browser, name, {"versioning": contract.versioning}, role, values, answers))
            check()
        return results
    finally:
        client.close()
        browser.close()


def probe_bucket(client, browser, bucket, descriptor, role, values, answers):
    from botocore.exceptions import ClientError
    key = ("staging/" if role == "private" else "") + "setup-probes/" + uuid.uuid4().hex
    payloads = (b"spaceworks-conditional-a", b"spaceworks-conditional-b")
    created = []

    def create(payload):
        try:
            result = client.put_object(Bucket=bucket, Key=key, Body=payload, IfNoneMatch="*", ContentType="application/octet-stream")
            created.append((payload, result.get("VersionId")))
            return True
        except ClientError as exc:
            if str(exc.response.get("Error", {}).get("Code")) in {"PreconditionFailed", "412", "ConditionalRequestConflict", "409"}:
                return None
            raise

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            # Track successful writes inside each future, including when another
            # future raises; an uncertain write is still cleaned by exact key.
            list(pool.map(create, payloads))
        if len(created) != 1:
            raise SetupError("conditional_create_unproven", "This store needs a verified native atomic-create adapter before it can be advertised complete.")
        result = client.get_object(Bucket=bucket, Key=key)
        with result["Body"] as body:
            payload = body.read(128)
        if payload != created[0][0]:
            raise SetupError("conditional_create_corrupt", "Storage conditional-create read-back failed; refuse launch.")
        params = {"Bucket": bucket, "Key": key}
        signed = browser.generate_presigned_url("get_object", Params=params, ExpiresIn=60)
        check_url(signed, payload)
        if role == "private":
            parts = urlsplit(signed)
            check_url(urlunsplit((parts.scheme, parts.netloc, parts.path, "", "")), None)
            method = answers.get("presign_method", "put").upper()
            if method == "POST":
                signed_post = browser.generate_presigned_post(Bucket=bucket, Key=key, Fields={"Content-Type": "application/octet-stream"}, Conditions=[{"Content-Type": "application/octet-stream"}, ["content-length-range", 1, len(payload)]], ExpiresIn=60)
                upload_url = signed_post["url"]
            else:
                upload_url = browser.generate_presigned_url("put_object", Params=dict(params, ContentType="application/octet-stream"), ExpiresIn=60)
            request = Request(upload_url, method="OPTIONS", headers={"Origin": answers["public_origin"], "Access-Control-Request-Method": method, "Access-Control-Request-Headers": "content-type"})
            with build_opener(NoRedirect).open(request, timeout=5) as response:
                if response.headers.get("Access-Control-Allow-Origin") != answers["public_origin"].rstrip("/"):
                    raise SetupError("storage_cors", "Configure exact frontend-origin upload CORS using the provider-supported dashboard/API.")
            if method == "POST":
                post_upload(signed_post, payload, oversized=False)
                post_upload(signed_post, payload + b"x", oversized=True)
        else:
            from .answers import https_url
            base = https_url(values.get("PUBLIC_IMAGE_BASE_URL", ""), "PUBLIC_IMAGE_BASE_URL")
            check_url(base.rstrip("/") + "/" + quote(key, safe="/"), payload)
        return {"role": role, "status": "passed", "conditional_create": True, "readback_sha256": hashlib.sha256(payload).hexdigest(), "versioning": descriptor["versioning"]}
    finally:
        # Delete only this attempt's exact key, including all versions. Do not use
        # prefix deletes or assume a PUT store has no history (notably B2).
        if descriptor["versioning"] != "never_versioned":
            for page in client.get_paginator("list_object_versions").paginate(Bucket=bucket, Prefix=key):
                for item in page.get("Versions", []) + page.get("DeleteMarkers", []):
                    if item["Key"] == key:
                        client.delete_object(Bucket=bucket, Key=key, VersionId=item["VersionId"])
            for page in client.get_paginator("list_object_versions").paginate(Bucket=bucket, Prefix=key):
                if any(item["Key"] == key for item in page.get("Versions", []) + page.get("DeleteMarkers", [])):
                    raise SetupError("probe_cleanup_failed", "Remove only the recorded setup-probes key versions and verify absence before retrying.")
        else:
            client.delete_object(Bucket=bucket, Key=key)
            try:
                client.head_object(Bucket=bucket, Key=key)
            except ClientError as exc:
                if str(exc.response.get("Error", {}).get("Code")) not in {"404", "NoSuchKey", "NotFound"}:
                    raise
            else:
                raise SetupError("probe_cleanup_failed", "Remove the exact setup-probes object and verify deletion before retrying.")


def check_url(url, expected):
    try:
        with build_opener(NoRedirect).open(Request(url), timeout=5) as response:
            if expected is None or response.read(128) != expected:
                raise SetupError("storage_delivery_policy", "Verify private/staging denial and correct public-final delivery; no automatic policy change is made.")
    except HTTPError as exc:
        try:
            if expected is None and exc.code in {403, 404}:
                return
            raise
        finally:
            exc.close()


def post_upload(signed, payload, *, oversized):
    boundary = "spaceworks-" + uuid.uuid4().hex
    parts = []
    for name, value in signed["fields"].items():
        parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'.encode())
    parts.extend([f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="probe.bin"\r\nContent-Type: application/octet-stream\r\n\r\n'.encode(), payload, f'\r\n--{boundary}--\r\n'.encode()])
    request = Request(signed["url"], data=b"".join(parts), method="POST", headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    try:
        with build_opener(NoRedirect).open(request, timeout=5) as response:
            if oversized or response.status not in {200, 201, 204}:
                raise SetupError("post_size_policy_unproven", "The selected store did not enforce the POST upload-time byte policy.")
    except HTTPError as exc:
        try:
            if oversized and exc.code in {400, 403}:
                return
            raise
        finally:
            exc.close()

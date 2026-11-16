"""Executable qualification; no unit simulation certifies a named provider.

Harness test uses disposable MinIO from dev.sh. Live tests require explicit
CLOUD_STORAGE_TEST_PROVIDER (r2|b2|supabase|s3) and TEST endpoint/region/bucket/key
variables below. Use a dedicated empty bucket with version/delete permissions.
No bucket, versioning, policy or lifecycle is provisioned by these tests.
"""

from dataclasses import replace
import os
import uuid
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import boto3
from botocore.client import Config
import pytest
from django.conf import settings

from apps.backup import storage
from apps.storage_capabilities.contracts import StorageIdentity
from apps.storage_capabilities.deletion import delete_exact_key
from apps.storage_capabilities.probes import inspect_bucket, probe_conditional_create
from apps.storage_capabilities.presigning import public_image_staging
from apps.storage_capabilities.upload_probes import probe_upload_methods
from apps.storage_capabilities.operation_probes import probe_object_lock
from apps.storage_capabilities.deletion import version_pages
from tests.cloud.storage.test_contracts import contract


@pytest.mark.django_db
def test_harness_minio_concurrent_create_and_version_cleanup(settings):
    settings.STORAGE_CAPABILITIES_FILE = ""
    s3 = storage.client()
    bucket = settings.AWS_STORAGE_BUCKET_NAME
    assert probe_conditional_create(s3, bucket=bucket)
    key = f"spaceworks-capability-probes/{uuid.uuid4().hex}"
    try:
        s3.put_object(Bucket=bucket, Key=key, Body=b"first")
        s3.put_object(Bucket=bucket, Key=key, Body=b"second")
        s3.delete_object(Bucket=bucket, Key=key)
        evidence = delete_exact_key(s3, bucket=bucket, key=key)
        assert evidence.absence_confirmed and evidence.versions_deleted >= 3
    finally:
        delete_exact_key(s3, bucket=bucket, key=key)


def test_live_named_store_conditional_create_and_history():
    provider = os.environ.get("CLOUD_STORAGE_TEST_PROVIDER")
    if provider is None:
        pytest.skip("Live account qualification requires explicit disposable-provider credentials.")
    assert provider in {"r2", "b2", "supabase", "s3"}
    required = {name: os.environ.get("CLOUD_STORAGE_TEST_" + name)
                for name in ("ENDPOINT", "REGION", "BUCKET", "ACCESS_KEY_ID", "SECRET_ACCESS_KEY")}
    assert all(required.values()), "Incomplete live provider fixture (values redacted)."
    s3 = boto3.client("s3", endpoint_url=required["ENDPOINT"], region_name=required["REGION"],
        aws_access_key_id=required["ACCESS_KEY_ID"], aws_secret_access_key=required["SECRET_ACCESS_KEY"],
        config=Config(signature_version="s3v4", s3={"addressing_style": "path"},
                      connect_timeout=5, read_timeout=10, retries={"total_max_attempts": 1}))
    history = provider in {"b2", "s3"}
    value = replace(contract(), identity=StorageIdentity.build(required["ENDPOINT"], required["REGION"], required["BUCKET"]),
                    versioning="enabled" if history else "never_versioned", list_delete_versions=history,
                    presign_methods=frozenset({"put", "post"} if provider == "s3" else {"put"}))
    facts = inspect_bucket(s3, value)
    assert facts["versioning"] == value.versioning
    # Header ignored or unsupported is a real failure, including on B2; no xfail.
    assert probe_conditional_create(s3, bucket=required["BUCKET"], never_versioned=not history)
    assert set(probe_upload_methods(s3, value)["presign_methods"]) == value.presign_methods


@pytest.mark.django_db
def test_harness_object_lock_retention_and_delete_denial():
    s3 = storage.client()
    bucket = "spaceworks-lock-probe-" + uuid.uuid4().hex
    s3.create_bucket(Bucket=bucket, ObjectLockEnabledForBucket=True)
    value = replace(contract(), identity=StorageIdentity.build(s3.meta.endpoint_url, s3.meta.region_name, bucket),
                    versioning="enabled", list_delete_versions=True, object_lock=True)
    try:
        result = probe_object_lock(s3, value, mode="GOVERNANCE")
        assert result["object_lock"] is True
        assert result["lock_probe_mode"] == "GOVERNANCE"
    finally:
        # This fresh disposable governance bucket belongs solely to this test.
        # Explicit bypass is cleanup authority; production probes never bypass.
        for page in version_pages(s3, bucket=bucket, prefix="spaceworks-capability-probes/"):
            for item in [*page.get("Versions", ()), *page.get("DeleteMarkers", ())]:
                s3.delete_object(Bucket=bucket, Key=item["Key"], VersionId=item["VersionId"],
                                 BypassGovernanceRetention=True)
        s3.delete_bucket(Bucket=bucket)


@pytest.mark.django_db
def test_harness_post_size_policy_and_mime_binding(settings):
    s3 = storage.client()
    bucket = settings.AWS_STORAGE_BUCKET_NAME
    key = f"spaceworks-capability-probes/{uuid.uuid4().hex}"
    signed = s3.generate_presigned_post(Bucket=bucket, Key=key,
        Fields={"Content-Type": "image/png"}, Conditions=[{"Content-Type": "image/png"},
        ["content-length-range", 1, 16]], ExpiresIn=60)
    try:
        assert _post(signed, b"valid", "image/png") in {200, 201, 204}
        assert _post(signed, b"x" * 17, "image/png") in {400, 403}
        assert _post(signed, b"valid", "application/pdf") in {400, 403}
    finally:
        delete_exact_key(s3, bucket=bucket, key=key)


@pytest.mark.django_db
def test_harness_private_staging_is_not_anonymous_and_signed_get_works(settings):
    s3 = storage.client()
    bucket = settings.AWS_STORAGE_BUCKET_NAME
    locator = public_image_staging(f"images/{uuid.uuid4().hex}", private_bucket=bucket)
    payload = b"private staging qualification"
    try:
        s3.put_object(Bucket=locator.bucket, Key=locator.key, Body=payload)
        url = s3.generate_presigned_url("get_object", Params={"Bucket": bucket, "Key": locator.key}, ExpiresIn=60)
        try:
            with urlopen(url, timeout=10) as response:
                assert response.read(1024) == payload
        except (HTTPError, URLError):
            raise AssertionError("Signed private staging probe failed (URL redacted).") from None
        try:
            # Stripping the signature query must lose access.
            with urlopen(url.split("?", 1)[0], timeout=10):
                pytest.fail("Private staging was anonymously readable.")
        except HTTPError as exc:
            assert exc.code in {403, 404}, "Unexpected anonymous-read result (URL redacted)."
        except URLError:
            raise AssertionError("Private staging probe transport failed (URL redacted).") from None
    finally:
        delete_exact_key(s3, bucket=bucket, key=locator.key)


def _post(signed, payload, mime):
    boundary = "spaceworks-" + uuid.uuid4().hex
    fields = {**signed["fields"], "Content-Type": mime}
    parts = []
    for key, value in fields.items():
        parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{key}"\r\n\r\n{value}\r\n'.encode())
    parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="probe.png"\r\nContent-Type: {mime}\r\n\r\n'.encode())
    parts.extend((payload, f"\r\n--{boundary}--\r\n".encode()))
    request = Request(signed["url"], data=b"".join(parts), method="POST",
                      headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    try:
        with urlopen(request, timeout=10) as response:
            return response.status
    except HTTPError as exc:
        return exc.code
    except URLError:
        raise AssertionError("POST qualification transport failed (URL redacted).") from None

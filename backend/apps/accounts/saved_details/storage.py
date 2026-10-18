"""Account-owned storage adapter; bounded SDK calls and no Events dependency."""
from datetime import timedelta
import hashlib

import boto3
from botocore.config import Config
from django.conf import settings
from django.utils import timezone

from apps.makerspaces.private_upload_transport import ObjectLocator, UploadDescriptor
from apps.object_storage import delete_all_versions

from .errors import SavedDetailsError, unavailable
from .pdf_validation import validate_pdf

MAX_RESUME_BYTES = 10 * 1024**2


def bucket():
    return settings.AWS_STORAGE_BUCKET_NAME


def client(*, public=False):
    return boto3.client(
        "s3", endpoint_url=settings.AWS_S3_PUBLIC_ENDPOINT_URL if public else settings.AWS_S3_ENDPOINT_URL,
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID, aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        region_name=settings.AWS_S3_REGION_NAME,
        config=Config(signature_version=settings.AWS_S3_SIGNATURE_VERSION, connect_timeout=2, read_timeout=2,
                      retries={"total_max_attempts": 1}, s3={"addressing_style": settings.AWS_S3_ADDRESSING_STYLE}),
    )


def initialize(asset):
    try:
        result = client(public=True).generate_presigned_post(
            Bucket=bucket(), Key=asset.staging_key, Fields={"Content-Type": "application/pdf"},
            Conditions=[{"Content-Type": "application/pdf"}, ["content-length-range", asset.size_bytes, asset.size_bytes]], ExpiresIn=600,
        )
        return UploadDescriptor(method="POST", url=result["url"], fields=result["fields"],
                                expires_at=timezone.now() + timedelta(minutes=10), generation=asset.generation)
    except Exception as exc:
        raise unavailable("storage_unavailable") from exc


def read_range(locator, *, start, length, timeout_seconds):
    kwargs = {"Bucket": locator.bucket, "Key": locator.key, "Range": f"bytes={start}-{start + length - 1}"}
    if locator.version_id:
        kwargs["VersionId"] = locator.version_id
    response = client().get_object(**kwargs)
    try:
        return response["Body"].read(length)
    finally:
        response["Body"].close()


def verify_resume(asset):
    """Snapshot staging before verification. A still-valid presign cannot replace it."""
    try:
        store = client()
        head = store.head_object(Bucket=bucket(), Key=asset.staging_key)
        if head["ContentLength"] != asset.size_bytes or asset.size_bytes > MAX_RESUME_BYTES:
            raise SavedDetailsError("invalid_upload_size", "Upload the declared PDF size.")
        source = {"Bucket": bucket(), "Key": asset.staging_key}
        if head.get("VersionId"):
            source["VersionId"] = head["VersionId"]
        store.copy_object(Bucket=bucket(), Key=asset.verification_key, CopySource=source, CopySourceIfMatch=head["ETag"])
        response = store.get_object(Bucket=bucket(), Key=asset.verification_key)
        try:
            data = response["Body"].read(MAX_RESUME_BYTES + 1)
        finally:
            response["Body"].close()
        if len(data) != asset.size_bytes or not data.startswith(b"%PDF-"):
            raise SavedDetailsError("invalid_pdf", "Upload a valid PDF résumé.")
        validate_pdf(data)
        scan_status = scan_pdf(data)
        result = store.put_object(Bucket=bucket(), Key=asset.object_key, Body=data, ContentType="application/pdf")
        return {"sha256": hashlib.sha256(data).hexdigest(), "scan_status": scan_status,
                "source_version_id": head.get("VersionId", ""), "final_version_id": result.get("VersionId", "")}
    except SavedDetailsError:
        raise
    except Exception as exc:
        raise unavailable("storage_unavailable") from exc


def scan_pdf(data):
    if not getattr(settings, "ACCOUNT_SAVED_RESUME_SCAN_REQUIRED", False):
        return "not_configured"
    scanner = getattr(settings, "ACCOUNT_SAVED_RESUME_SCANNER", None)
    if scanner is None:
        raise unavailable("scanner_unavailable")
    try:
        result = scanner(data)
    except Exception as exc:
        raise unavailable("scanner_unavailable") from exc
    if result != "clean":
        raise SavedDetailsError("unsafe_pdf", "The résumé did not pass the file safety check.")
    return "clean"


def delete_keys(keys):
    for key in keys:
        delete_all_versions(client(), bucket=bucket(), key=key, require_version_listing=True)


def put_archive(key, data):
    try:
        client().put_object(Bucket=bucket(), Key=key, Body=data, ContentType="application/zip")
    except Exception as exc:
        raise unavailable("storage_unavailable") from exc

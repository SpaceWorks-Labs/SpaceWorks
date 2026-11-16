from apps.storage_clients import s3_client
"""Bounded server-side logo retention. No URLs or source version ids enter documents."""

import hashlib
from io import BytesIO
import logging

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError
from django.conf import settings

logger = logging.getLogger(__name__)
MAX_SOURCE_BYTES = 5 * 1024 * 1024
MAX_LOGO_BYTES = 256 * 1024


def _client():
    return s3_client("s3", endpoint_url=settings.AWS_S3_ENDPOINT_URL,
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID, aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        region_name=settings.AWS_S3_REGION_NAME, config=Config(
            connect_timeout=3, read_timeout=3, retries={"total_max_attempts": 1},
            signature_version=settings.AWS_S3_SIGNATURE_VERSION,
            s3={"addressing_style": settings.AWS_S3_ADDRESSING_STYLE}))


def _read(client, bucket, key, limit):
    response = client.get_object(Bucket=bucket, Key=key)
    body = response["Body"]
    try:
        if response.get("ContentLength", 0) > limit:
            raise ValueError("Logo exceeds the size limit.")
        data = body.read(limit + 1)
        if len(data) > limit:
            raise ValueError("Logo exceeds the size limit.")
        return data
    finally:
        body.close()


def normalize_logo(data):
    from PIL import Image
    with Image.open(BytesIO(data)) as image:
        # Every public-image logo format (PUBLIC_IMAGE_ALLOWED_MIME) is accepted, then normalised to PNG.
        if image.format not in ("PNG", "JPEG", "WEBP") or image.width * image.height > 16_000_000:
            raise ValueError("Unsupported logo.")
        image.thumbnail((600, 300), Image.Resampling.LANCZOS)
        output = BytesIO()
        image = image.convert("RGBA")
        image.save(output, format="PNG", optimize=True)
        if output.tell() > MAX_LOGO_BYTES:
            output = BytesIO()
            image.quantize(colors=128, method=Image.Quantize.FASTOCTREE).save(output, format="PNG", optimize=True)
    result = output.getvalue()
    if len(result) > MAX_LOGO_BYTES:
        raise ValueError("Logo exceeds the retained size limit.")
    return result


def retain_logo(space):
    if not space.logo_key:
        return "", ""
    try:
        client = _client()
        data = normalize_logo(_read(client, settings.PUBLIC_IMAGE_BUCKET, space.logo_key, MAX_SOURCE_BYTES))
        digest = hashlib.sha256(data).hexdigest()
        key = f"billing-branding/{space.pk}/{digest}.png"
        try:
            client.put_object(Bucket=settings.AWS_STORAGE_BUCKET_NAME, Key=key, Body=data,
                              ContentType="image/png", IfNoneMatch="*")
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") not in ("PreconditionFailed", "412"):
                raise
        return key, digest
    except Exception as exc:
        logger.warning("billing_logo_retention_failed", extra={
            "makerspace_id": space.pk, "failure_type": type(exc).__name__,
        })
        return "", ""


def load_logo(document):
    key = getattr(document, "branding_logo_key", "")
    if not key:
        return None
    try:
        data = _read(_client(), settings.AWS_STORAGE_BUCKET_NAME, key, MAX_LOGO_BYTES)
        if hashlib.sha256(data).hexdigest() != document.branding_logo_sha256:
            raise ValueError("Retained logo digest mismatch.")
        from PIL import Image
        with Image.open(BytesIO(data)) as image:
            if image.format != "PNG" or image.width > 600 or image.height > 300:
                raise ValueError("Invalid retained logo.")
            image.verify()
        return data
    except Exception as exc:
        logger.warning("billing_logo_read_failed", extra={
            "document_id": document.pk, "failure_type": type(exc).__name__,
        })
        return None

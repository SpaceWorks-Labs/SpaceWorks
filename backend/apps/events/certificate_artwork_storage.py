"""Bounded private artwork staging; final keys are write-once and server-owned."""

import hashlib
from io import BytesIO
import warnings

from botocore.exceptions import BotoCoreError, ClientError
from django.conf import settings
from PIL import Image, UnidentifiedImageError
from rest_framework.exceptions import APIException, ValidationError

from apps.evidence.image_validation import image_mime_from_bytes
from apps.events.certificate_storage import _client, staging_key
from apps.object_storage import delete_all_versions

MAX_BYTES = 10 * 1024 * 1024
MAX_PIXELS = 16_000_000


class ArtworkUnavailable(APIException):
    status_code = 503
    default_detail = "Certificate artwork storage is temporarily unavailable."
    default_code = "artwork_storage_unavailable"


def upload_url(row, *, content_type, content_length):
    try:
        return _client(settings.AWS_S3_PUBLIC_ENDPOINT_URL).generate_presigned_url(
            "put_object", Params={"Bucket": settings.AWS_STORAGE_BUCKET_NAME,
                                  "Key": staging_key(row.object_key), "ContentType": content_type,
                                  "ContentLength": content_length}, ExpiresIn=600,
        )
    except (BotoCoreError, ClientError) as exc:
        raise ArtworkUnavailable from exc


def _read(client, key, version=""):
    params = {"Bucket": settings.AWS_STORAGE_BUCKET_NAME, "Key": key}
    if version and version != "null":
        params["VersionId"] = version
    try:
        response = client.get_object(**params)
    except ClientError as exc:
        # Restored private bytes have a new provider version. The immutable
        # checksum in read_artwork still proves the exact issuance-time object.
        if not version or exc.response.get("Error", {}).get("Code") not in {"NoSuchVersion", "NoSuchKey", "404"}:
            raise
        params.pop("VersionId", None)
        response = client.get_object(**params)
    body = response["Body"]
    try:
        content = body.read(MAX_BYTES + 1)
    finally:
        body.close()
    if not content or len(content) > MAX_BYTES:
        raise ValidationError({"artwork": "Artwork must be at most 10 MiB."})
    return content, response.get("VersionId", "")


def _png(content):
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            if image_mime_from_bytes(content) not in ("image/png", "image/jpeg"):
                raise ValidationError({"artwork": "Upload a PNG or JPEG image."})
            with Image.open(BytesIO(content)) as image:
                if image.width * image.height > MAX_PIXELS or getattr(image, "n_frames", 1) != 1:
                    raise ValidationError({"artwork": "Use one image with at most 16 million pixels."})
                image.load()
                output = BytesIO()
                with image.convert("RGBA") as pixels:
                    # Fresh pixels preserve transparent logo/signature layers and
                    # strip EXIF/ICC/text metadata before immutable promotion.
                    pixels.info.clear()
                    pixels.save(output, format="PNG")
                result = output.getvalue()
                if len(result) > MAX_BYTES:
                    raise ValidationError({"artwork": "Decoded artwork exceeds 10 MiB."})
                return result
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError,
            Image.DecompressionBombWarning, ValueError) as exc:
        raise ValidationError({"artwork": "Invalid artwork image."}) from exc


def promote_bytes(row):
    """Outside DB locks. Conditional put makes a live staging presign harmless."""
    client = _client(settings.AWS_S3_ENDPOINT_URL)
    try:
        content, _version = _read(client, staging_key(row.object_key))
        payload = _png(content)
        try:
            client.put_object(Bucket=settings.AWS_STORAGE_BUCKET_NAME, Key=row.object_key,
                              Body=payload, ContentType="image/png", IfNoneMatch="*")
        except ClientError as exc:
            if exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode") != 412:
                raise
        # On a retry the first canonical promotion wins, even if staging changed.
        stored, version = _read(client, row.object_key)
        _png(stored)
        return len(stored), hashlib.sha256(stored).hexdigest(), version
    except ClientError as exc:
        if exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode") == 404:
            raise ValidationError({"artwork": "Upload artwork before finalizing it."}) from exc
        raise ArtworkUnavailable from exc
    except (BotoCoreError, OSError) as exc:
        raise ArtworkUnavailable from exc


def read_artwork(key, version, digest):
    try:
        payload, _version = _read(_client(settings.AWS_S3_ENDPOINT_URL), key, version)
        if hashlib.sha256(payload).hexdigest() != digest:
            raise ArtworkUnavailable("Artwork failed its immutable checksum check.")
        return payload
    except (BotoCoreError, ClientError, OSError) as exc:
        raise ArtworkUnavailable from exc


def cleanup_staging(row):
    try:
        delete_all_versions(_client(settings.AWS_S3_ENDPOINT_URL),
                            bucket=settings.AWS_STORAGE_BUCKET_NAME, key=staging_key(row.object_key))
    except (BotoCoreError, ClientError, OSError):
        import logging
        logging.getLogger(__name__).warning("certificate_artwork_staging_cleanup_failed",
                                            extra={"artwork_id": row.pk})

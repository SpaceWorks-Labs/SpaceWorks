"""Private issue photos: every presign lands on the STAGING key (Hard Rule).

The client never writes the final key. Attaching a photo promotes the staged object to
its final key exactly once, then checks it really is a JPEG, PNG or WebP image under the
evidence size limit. Reads are short-lived signed URLs on the private bucket.
"""

from django.utils.translation import gettext
import sys
import uuid

from botocore.exceptions import BotoCoreError, ClientError
from django.conf import settings
from rest_framework.exceptions import ValidationError

from apps.evidence.storage import StorageUnavailable
from apps.maintenance import storage as shared

EXTENSIONS = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}


def _client():
    return shared._client()


def _public_client():
    return shared._public_client()


def object_size(object_key):
    return shared.object_size(object_key)


def staging_key(final_key):
    return f"staging/{final_key}"


def max_bytes():
    return settings.EVIDENCE_MAX_BYTES


def photo_key(makerspace_id, content_type):
    if content_type not in EXTENSIONS:
        raise ValidationError({"content_type": gettext("Upload a JPEG, PNG or WebP photo.")})
    return f"repairs/{makerspace_id}/{uuid.uuid4().hex}.{EXTENSIONS[content_type]}"


def owns_key(object_key, makerspace_id):
    prefix = f"repairs/{makerspace_id}/"
    rest = str(object_key or "")[len(prefix):]
    return str(object_key or "").startswith(prefix) and rest and "/" not in rest


def presign(object_key, content_type):
    try:
        if getattr(settings, "STORAGE_CAPABILITIES_FILE", ""):
            from apps.private_uploads import presign as capability_presign
            return capability_presign(sys.modules[__name__], object_key, content_type, max_bytes())
        if settings.STORAGE_PRESIGN_METHOD == "put":
            url = _public_client().generate_presigned_url(
                "put_object", ExpiresIn=settings.EVIDENCE_URL_TTL_SECONDS,
                Params={"Bucket": settings.AWS_STORAGE_BUCKET_NAME, "Key": staging_key(object_key),
                        "ContentType": content_type})
            return {"url": url, "method": "PUT", "headers": {"Content-Type": content_type}}
        return _public_client().generate_presigned_post(
            Bucket=settings.AWS_STORAGE_BUCKET_NAME, Key=staging_key(object_key),
            Fields={"Content-Type": content_type},
            Conditions=[{"Content-Type": content_type}, ["content-length-range", 1, max_bytes()]],
            ExpiresIn=settings.EVIDENCE_URL_TTL_SECONDS)
    except (BotoCoreError, ClientError) as exc:
        raise StorageUnavailable from exc


def finalize(object_key):
    """Promote staging -> final once; return the final size, or None if never uploaded."""
    if getattr(settings, "STORAGE_CAPABILITIES_FILE", ""):
        from apps.private_uploads import finalize as capability_finalize
        return capability_finalize(sys.modules[__name__], object_key, max_bytes())
    existing = object_size(object_key)
    if existing is not None:
        return existing
    source = staging_key(object_key)
    size = object_size(source)
    if size is None or not (1 <= size <= max_bytes()):
        return size
    try:
        _client().copy_object(Bucket=settings.AWS_STORAGE_BUCKET_NAME, Key=object_key,
                              CopySource={"Bucket": settings.AWS_STORAGE_BUCKET_NAME, "Key": source})
    except (BotoCoreError, ClientError) as exc:
        raise StorageUnavailable from exc
    shared.delete_object(source)
    return object_size(object_key)


def validated_photo(object_key):
    """(size, content type) of a promoted photo, or a 400 naming what is wrong."""
    size = finalize(object_key)
    if size is None:
        raise ValidationError({"photos": gettext("A photo was not uploaded yet.")})
    if not 1 <= size <= max_bytes():
        raise ValidationError({"photos": gettext("A photo is empty or too large.")})
    try:
        body = _client().get_object(Bucket=settings.AWS_STORAGE_BUCKET_NAME, Key=object_key)["Body"].read(64)
    except (BotoCoreError, ClientError, OSError) as exc:
        raise StorageUnavailable from exc
    from apps.maker_formats.legacy import sniff_pdf_or_image
    sniffed = sniff_pdf_or_image(body)
    if sniffed not in EXTENSIONS or EXTENSIONS[sniffed] != object_key.rsplit(".", 1)[-1]:
        raise ValidationError({"photos": gettext("A photo is not the image type it claimed to be.")})
    return size, sniffed


def signed_url(object_key):
    return shared.presigned_get_url(object_key)


def delete(object_key):
    shared.delete_object(object_key)
    shared.delete_object(staging_key(object_key))

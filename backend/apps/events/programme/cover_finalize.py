"""Re-encode an uploaded event or series cover as metadata-free WebP before it is attached.

The presigned upload still lands on a staging key and is promoted by `public_image_storage.finalize_upload`
(size cap, magic-byte sniff). This step then replaces the promoted object with a canonical WebP under a new
`.webp` key so that the attached key, and therefore the storage charge made by `limits.charge_upload`, always
describes the stripped bytes. The original object is deleted; nothing outside this makerspace's prefix is touched.
"""

from botocore.exceptions import BotoCoreError, ClientError
from django.conf import settings
from django.utils.translation import gettext
from rest_framework.exceptions import ValidationError

from apps.evidence.storage import StorageUnavailable
from apps.inventory import public_image_storage
from apps.storage_capabilities import CapabilityError

from .cover import canonical_cover_webp


def _read(object_key):
    try:
        response = public_image_storage._client().get_object(
            Bucket=settings.PUBLIC_IMAGE_BUCKET, Key=object_key)
        try:
            return response["Body"].read(settings.PUBLIC_IMAGE_MAX_BYTES + 1)
        finally:
            response["Body"].close()
    except (BotoCoreError, ClientError, OSError, CapabilityError) as exc:
        raise StorageUnavailable from exc


def _discard(object_key):
    public_image_storage.delete_object(object_key)
    public_image_storage.delete_object(public_image_storage.staging_key(object_key))


def claim_cover(object_key):
    """Commit the normalized destination before promotion or normalization writes.

    The HTTP attachment deliberately has no outer atomic block: this receipt must
    survive a later quota, audit or attachment failure.
    """
    from apps.makerspaces.storage_reservations import record_final_key
    base = object_key.rsplit(".", 1)[0] if "." in object_key.rsplit("/", 1)[-1] else object_key
    key = f"{base}.normalized.webp" if object_key.endswith(".webp") else f"{base}.webp"
    return record_final_key(object_key, key) or key


def convert_to_webp(object_key):
    """Return the key of the stripped WebP copy; the uploaded object is removed.

    Raises ValidationError (original object deleted) for an undecodable image and StorageUnavailable
    when the bucket cannot be reached.
    """
    new_key = claim_cover(object_key)
    data = _read(object_key)
    try:
        webp = canonical_cover_webp(data, max_bytes=settings.PUBLIC_IMAGE_MAX_BYTES)
    except ValidationError:
        _discard(object_key)
        raise ValidationError({"object_key": gettext("Uploaded file is not a valid image.")}) from None
    try:
        public_image_storage._client().put_object(
            Bucket=settings.PUBLIC_IMAGE_BUCKET, Key=new_key, Body=webp,
            ContentType="image/webp", IfNoneMatch="*",
        )
    except ClientError as exc:
        if str(exc.response.get("Error", {}).get("Code")) not in {
            "PreconditionFailed", "412", "ConditionalRequestConflict", "409",
        }:
            raise StorageUnavailable from exc
        # A concurrent normalizer won. Validate its immutable snapshot, never
        # replace it with the bytes this caller happened to read from staging.
        winner = _read(new_key)
        if not winner.startswith(b"RIFF") or winner[8:12] != b"WEBP":
            raise StorageUnavailable("Invalid normalized cover snapshot.")
        canonical_cover_webp(winner, max_bytes=settings.PUBLIC_IMAGE_MAX_BYTES)
    except (BotoCoreError, OSError, CapabilityError) as exc:
        raise StorageUnavailable from exc
    if new_key != object_key:
        from apps.object_storage import delete_all_versions
        try:
            removed = delete_all_versions(public_image_storage._client(),
                bucket=settings.PUBLIC_IMAGE_BUCKET, key=object_key)
            if not removed.absence_confirmed:
                raise StorageUnavailable("Upload deletion was not confirmed.")
        except (BotoCoreError, ClientError, OSError, CapabilityError) as exc:
            raise StorageUnavailable from exc
    return new_key

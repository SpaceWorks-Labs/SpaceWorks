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

from .cover import canonical_cover_webp


def _read(object_key):
    try:
        response = public_image_storage._client().get_object(
            Bucket=settings.PUBLIC_IMAGE_BUCKET, Key=object_key)
        return response["Body"].read(settings.PUBLIC_IMAGE_MAX_BYTES + 1)
    except (BotoCoreError, ClientError, OSError) as exc:
        raise StorageUnavailable from exc


def _discard(object_key):
    public_image_storage.delete_object(object_key)
    public_image_storage.delete_object(public_image_storage.staging_key(object_key))


def convert_to_webp(object_key):
    """Return the key of the stripped WebP copy; the uploaded object is removed.

    Raises ValidationError (original object deleted) for an undecodable image and StorageUnavailable
    when the bucket cannot be reached.
    """
    data = _read(object_key)
    try:
        webp = canonical_cover_webp(data, max_bytes=settings.PUBLIC_IMAGE_MAX_BYTES)
    except ValidationError:
        _discard(object_key)
        raise ValidationError({"object_key": gettext("Uploaded file is not a valid image.")}) from None
    base = object_key.rsplit(".", 1)[0] if "." in object_key.rsplit("/", 1)[-1] else object_key
    new_key = f"{base}.webp"
    public_image_storage.put_bytes(new_key, webp, "image/webp")
    if new_key != object_key:
        public_image_storage.delete_object(object_key)
    return new_key

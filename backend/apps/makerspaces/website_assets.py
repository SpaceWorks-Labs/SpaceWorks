"""Private, bounded website images. Domain adapters own rows and authorization.

Uploads are multipart, never client-chosen keys or writable final-key presigns.
Event callers reserve durable object intents, then work outside transactions and
attach in a separate locked commit. Bookings retains its existing clone boundary.
"""

from django.utils.translation import gettext
from io import BytesIO
import warnings
from uuid import uuid4

from botocore.exceptions import BotoCoreError, ClientError
from django.conf import settings
from PIL import Image, ImageOps, UnidentifiedImageError
from rest_framework.exceptions import ValidationError

from apps.evidence import storage
from apps.inventory.public_image_sniff import image_mime_from_bytes
from apps.inventory.public_image_storage import is_safe_object_key
from apps.makerspaces import limits
from apps.makerspaces.resource_clone import OwnedImage

MAX_BYTES = 5_000_000
MAX_PIXELS = 16_000_000
MAX_EDGE = 2048


def prefix(module, tenant_id, page_id):
    if module not in {"events", "bookings"}:
        raise ValueError("Unknown website asset domain.")
    return f"{module}/website/{int(tenant_id)}/{int(page_id)}/"


def owns(key, module, tenant_id, page_id, *, asset=None):
    if not is_safe_object_key(key):
        return False
    if key.startswith(prefix(module, tenant_id, page_id)):
        return True
    # Portable imports use the existing collision-safe object journal. Its verified
    # key mapping is the ownership proof when source page/tenant IDs have changed.
    if (asset is None or asset._meta.app_label != module or asset.object_key != key
            or asset.page_id != page_id or asset.page.makerspace_id != tenant_id):
        return False
    from apps.tenant_migration.models_import_objects import TenantImportObject
    return TenantImportObject.objects.filter(
        target_key=key, bucket_kind="private", job__target_makerspace_id=tenant_id,
        state__in=["promoted", "verified"],
    ).exists()


def webp(data):
    if not data or len(data) > MAX_BYTES:
        raise ValidationError({"file": gettext("Use an image up to 5 MB.")})
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            # Check dimensions BEFORE verify/decode, including byte-sniff verification.
            with Image.open(BytesIO(data)) as probe:
                if probe.width * probe.height > MAX_PIXELS or getattr(probe, "n_frames", 1) != 1:
                    raise ValueError("Image dimensions or frame count exceed the limit.")
            if image_mime_from_bytes(data) not in {"image/jpeg", "image/png", "image/webp"}:
                raise ValueError("Unsupported image.")
            with Image.open(BytesIO(data)) as source:
                source.load()
                image = ImageOps.exif_transpose(source).convert("RGBA")
                image.thumbnail((MAX_EDGE, MAX_EDGE))
                output = BytesIO()
                # No EXIF, ICC, comments, scripts or original filename survive.
                image.save(output, format="WEBP", quality=85)
                result = output.getvalue()
                if len(result) > MAX_BYTES:
                    raise ValueError("Converted image is too large.")
                return result
    except (OSError, ValueError, UnidentifiedImageError, Image.DecompressionBombError,
            Image.DecompressionBombWarning) as exc:
        raise ValidationError({"file": gettext("Use a single-frame JPEG, PNG or WebP up to 16 megapixels.")}) from exc


def delete_object(key):
    storage.delete_object_strict(key)
    return True


def object_size(key):
    return storage.object_size(key)


def copy_object(source, target):
    storage.copy_object(source, target)


def _put(key, data, content_type):
    try:
        storage._client().put_object(Bucket=settings.AWS_STORAGE_BUCKET_NAME,
                                     Key=key, Body=data, ContentType=content_type)
    except (BotoCoreError, ClientError, OSError) as exc:
        raise storage.StorageUnavailable from exc


def upload(file, *, module, page, copies):
    if module == "events":
        return copies.upload(file, page)
    data = file.read(MAX_BYTES + 1)
    converted = webp(data)
    key = prefix(module, page.makerspace_id, page.pk) + uuid4().hex + ".webp"
    staged = "staging/" + key
    import sys
    this = sys.modules[__name__]
    limits.add_storage(page.makerspace, len(converted))
    copies.created.extend(((this, staged), (this, key)))
    _put(staged, data, "application/octet-stream")
    _put(key, converted, "image/webp")
    # If deletion fails the transaction refuses, and the rollback cleanup retries.
    delete_object(staged)
    return key, len(converted)


def copy_asset(asset, destination, *, module, copies):
    import sys
    if not owns(asset.object_key, module, asset.page.makerspace_id, asset.page_id, asset=asset):
        raise ValidationError(gettext("Image is not owned by the source page."))
    if module != "events" and object_size(asset.object_key) != asset.size_bytes:
        raise ValidationError(gettext("The source image metadata does not match its private bytes."))
    return copies.copy_image(destination.makerspace, OwnedImage(
        asset.object_key, asset.object_key.rsplit("/", 1)[0] + "/",
        prefix(module, destination.makerspace_id, destination.pk), MAX_BYTES,
    ), storage=sys.modules[__name__], **({"journal_page": destination,
        "expected_size": asset.size_bytes} if module == "events" else {}))


def release(makerspace, key, size):
    """Only a confirmed byte deletion releases quota; callers schedule post-commit."""
    delete_object(key)
    limits.free_storage(makerspace, size)

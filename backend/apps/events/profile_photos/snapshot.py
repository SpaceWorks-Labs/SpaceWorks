"""Read one exact, server-selected avatar outside locks; never follow a caller URL."""

import hashlib
from dataclasses import dataclass, field
from io import BytesIO
import warnings

from botocore.exceptions import BotoCoreError, ClientError
from django.conf import settings
from PIL import Image, UnidentifiedImageError
from rest_framework.exceptions import APIException

from .selection_workflow import source_revision
from apps.transaction_guards import in_domain_transaction

MAX_BYTES = 10 * 1024 * 1024
MAX_PIXELS = 16_000_000


class PhotoUnavailable(APIException):
    status_code = 503
    default_detail = "The selected image is temporarily unavailable."
    default_code = "photo_unavailable"


@dataclass(frozen=True, kw_only=True)
class PreparedPhoto:
    profile_id: int
    membership_id: int
    source_revision: str
    source_key_digest: str
    sha256: str
    pixels: bytes = field(repr=False)


def canonical_png(content):
    if not content or len(content) > MAX_BYTES:
        raise PhotoUnavailable()
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(content)) as image:
                if (image.format not in ("PNG", "JPEG", "WEBP") or image.width * image.height > MAX_PIXELS
                        or getattr(image, "n_frames", 1) != 1):
                    raise PhotoUnavailable()
                image.load()
                image.thumbnail((1200, 1200))
                output = BytesIO()
                with image.convert("RGBA") as pixels:
                    pixels.info.clear()
                    pixels.save(output, format="PNG")
                result = output.getvalue()
                if len(result) > MAX_BYTES:
                    raise PhotoUnavailable()
                return result
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError,
            Image.DecompressionBombWarning) as exc:
        raise PhotoUnavailable() from exc


def prepare_photo(profile):
    if in_domain_transaction():
        raise RuntimeError("Prepare photo bytes outside domain transactions.")
    key, revision = profile.avatar_key, source_revision(profile)
    pixels = read_public_png(key)
    return PreparedPhoto(profile_id=profile.pk, membership_id=profile.membership_id,
                         source_revision=revision, source_key_digest=hashlib.sha256(key.encode()).hexdigest(),
                         sha256=hashlib.sha256(pixels).hexdigest(), pixels=pixels)


def read_public_png(key):
    if in_domain_transaction():
        raise RuntimeError("Read render resources outside domain transactions.")
    from apps.events.certificate_storage import _client as bounded_client
    try:
        response = bounded_client(settings.AWS_S3_ENDPOINT_URL).get_object(Bucket=settings.PUBLIC_IMAGE_BUCKET, Key=key)
        body = response["Body"]
        try:
            pixels = canonical_png(body.read(MAX_BYTES + 1))
        finally:
            body.close()
    except (BotoCoreError, ClientError, OSError) as exc:
        raise PhotoUnavailable() from exc
    return pixels

"""Image normalisation for card artwork and photos: sniffed type, re-encoded, no metadata.

Uploads are PNG/JPEG/WebP up to 8 MB (SPEC §3.2, §6). They are decoded with Pillow,
EXIF-rotated, resized to a bounded longest edge and re-encoded, which strips every
metadata block (GPS included). The mean colour feeds the contrast check.
"""
from io import BytesIO

from rest_framework.exceptions import ValidationError

ALLOWED = {"image/png": "PNG", "image/jpeg": "JPEG", "image/webp": "WEBP"}
MAX_UPLOAD_BYTES = 8 * 1024 * 1024
MAX_PUBLIC_BYTES = 8 * 1024 * 1024


def normalise(data, *, max_edge=2400, keep_alpha=True):
    """-> (png_bytes, width, height, mean_hex). Raises ValidationError for anything else."""
    from PIL import Image, ImageOps, UnidentifiedImageError
    if not data or len(data) > MAX_UPLOAD_BYTES:
        raise ValidationError({"file": "Upload a PNG, JPEG or WebP image up to 8 MB."})
    try:
        with Image.open(BytesIO(data)) as source:
            if source.format not in ALLOWED.values():
                raise ValidationError({"file": "Upload a PNG, JPEG or WebP image."})
            if source.width * source.height > 40_000_000:
                raise ValidationError({"file": "That image is too large."})
            image = ImageOps.exif_transpose(source)
            image = image.convert("RGBA" if keep_alpha else "RGB")
    except UnidentifiedImageError:
        raise ValidationError({"file": "That file isn't a readable image."}) from None
    image.thumbnail((max_edge, max_edge))
    buffer = BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    small = image.convert("RGB").resize((1, 1))
    mean = "#" + "".join(f"{value:02X}" for value in small.getpixel((0, 0)))
    return buffer.getvalue(), image.width, image.height, mean


def read_public_image(key):
    """A space/organisation/event logo from the public image bucket, as PNG, or None."""
    if not key:
        return None
    from botocore.exceptions import BotoCoreError, ClientError
    from django.conf import settings
    from apps.evidence.storage import _s3_client
    body = None
    try:
        body = _s3_client(settings.AWS_S3_ENDPOINT_URL).get_object(Bucket=settings.PUBLIC_IMAGE_BUCKET, Key=key)["Body"]
        data = body.read(MAX_PUBLIC_BYTES + 1)
    except (BotoCoreError, ClientError, OSError):
        return None
    finally:
        if body is not None:
            body.close()
    if len(data) > MAX_PUBLIC_BYTES:
        return None
    try:
        return normalise(data, max_edge=800)[0]
    except ValidationError:
        return None

"""Bounded cover canonicalization for G's existing image-attach transport."""

from django.utils.translation import gettext
from io import BytesIO
import warnings

from PIL import Image, ImageOps, UnidentifiedImageError
from rest_framework.exceptions import ValidationError


MAX_BYTES = 5 * 1024 * 1024
MAX_PIXELS = 16_000_000


def canonical_cover(data):
    """Sniff bytes, orient and re-encode without EXIF. Claimed MIME is not an input.

    G applies this before promoting/attaching through the existing bounded upload
    workflow; authored page covers still use revision-owned private assets.
    """
    if not isinstance(data, bytes) or not data or len(data) > MAX_BYTES:
        raise ValidationError({"image": gettext("Use an image of at most 5 MiB.")})
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(data)) as source:
                if source.format not in {"JPEG", "PNG", "WEBP"} or getattr(source, "n_frames", 1) != 1:
                    raise ValueError("Unsupported image.")
                if source.width * source.height > MAX_PIXELS:
                    raise ValueError("Image dimensions are too large.")
                source.load()
                normalized = ImageOps.exif_transpose(source).convert("RGBA")
                normalized.thumbnail((2048, 2048))
                # New pixel-only image avoids copying source EXIF/XMP/ICC metadata.
                clean = Image.new("RGBA", normalized.size)
                clean.paste(normalized)
                output = BytesIO()
                clean.save(output, format="PNG", optimize=True)
    except (ValueError, OSError, UnidentifiedImageError, Image.DecompressionBombError,
            Image.DecompressionBombWarning) as exc:
        raise ValidationError({"image": gettext("Use a valid, single-frame image of at most 16 megapixels.")}) from exc
    result = output.getvalue()
    if len(result) > MAX_BYTES:
        raise ValidationError({"image": gettext("The normalized image exceeds 5 MiB.")})
    return result

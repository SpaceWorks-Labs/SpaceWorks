"""One-frame, bounded, metadata-free canonical images (hash after conversion)."""
from io import BytesIO
import warnings

from PIL import Image, UnidentifiedImageError

from .errors import FormatError


def canonical_image(data, *, expected_mime):
    formats = {"image/jpeg": "JPEG", "image/png": "PNG", "image/webp": "WEBP"}
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(data)) as original:
                if (original.width * original.height > 16_000_000 or
                        getattr(original, "n_frames", 1) != 1 or
                        original.format != formats.get(expected_mime)):
                    raise FormatError("invalid_image")
                original.verify()
            with Image.open(BytesIO(data)) as image:
                converted = image.convert("RGB" if expected_mime == "image/jpeg" else "RGBA")
                # Fresh image prevents EXIF/ICC/comment dictionaries from surviving.
                clean = Image.new(converted.mode, converted.size)
                clean.frombytes(converted.tobytes())
                output = BytesIO()
                clean.save(output, format=formats[expected_mime])
                return output.getvalue()
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError,
            Image.DecompressionBombWarning) as exc:
        raise FormatError("invalid_image") from exc

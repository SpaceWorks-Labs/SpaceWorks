"""E-B7 covers: decoded, bounded, stripped of metadata and stored as WebP."""
from io import BytesIO

import pytest
from PIL import Image
from rest_framework.exceptions import ValidationError

from apps.events.programme.cover import MAX_BYTES, canonical_cover_webp


def _jpeg_with_exif(size=(120, 80)):
    image = Image.new("RGB", size, (200, 30, 30))
    exif = Image.Exif()
    exif[0x010F] = "SecretCameraMaker"  # Make
    output = BytesIO()
    image.save(output, format="JPEG", exif=exif)
    return output.getvalue()


def test_output_is_webp_without_exif():
    source = _jpeg_with_exif()
    assert b"SecretCameraMaker" in source
    result = canonical_cover_webp(source)
    with Image.open(BytesIO(result)) as image:
        assert image.format == "WEBP"
        assert not image.getexif()
        assert "exif" not in image.info and "icc_profile" not in image.info
    assert b"SecretCameraMaker" not in result


def test_large_images_are_capped_at_2048():
    output = BytesIO()
    Image.new("RGB", (4000, 1000), (1, 2, 3)).save(output, format="PNG")
    with Image.open(BytesIO(canonical_cover_webp(output.getvalue()))) as image:
        assert max(image.size) == 2048


@pytest.mark.parametrize("data", [b"", b"not an image", b"GIF89a" + b"\x00" * 40])
def test_undecodable_bytes_are_refused(data):
    with pytest.raises(ValidationError):
        canonical_cover_webp(data)


def test_input_over_the_bound_is_refused():
    with pytest.raises(ValidationError):
        canonical_cover_webp(b"\x00" * (MAX_BYTES + 1))
    with pytest.raises(ValidationError):
        canonical_cover_webp(_jpeg_with_exif(), max_bytes=10)

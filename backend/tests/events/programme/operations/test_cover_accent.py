from io import BytesIO

from django.core.exceptions import ValidationError as SchemaError
from PIL import Image
import pytest
from rest_framework.exceptions import ValidationError

from apps.events.programme.accent_presets import ACCENT_PRESETS, project_accent, validate_accent_preset
from apps.events.programme.cover import MAX_BYTES, canonical_cover


@pytest.mark.parametrize("value", ["#006E63", "teal", "", 1, {"color": "#006E63"}])
def test_only_named_brand_accents_are_accepted(value):
    with pytest.raises(SchemaError):
        validate_accent_preset(value)
    assert project_accent(value) is None


def test_every_preset_has_approved_high_contrast_foreground_and_inheritance():
    assert validate_accent_preset(None) is None
    for key, palette in ACCENT_PRESETS.items():
        assert validate_accent_preset(key) == key
        assert palette["foreground"] == ("#FFF4E8" if key == "maker_teal" else "#142C2A")


def test_cover_sniffs_bytes_and_drops_exif_even_with_valid_jpeg():
    source = Image.new("RGB", (30, 20), "red")
    exif = Image.Exif()
    exif[0x010E] = "private camera note"
    output = BytesIO()
    source.save(output, format="JPEG", exif=exif)
    data = canonical_cover(output.getvalue())
    with Image.open(BytesIO(data)) as image:
        assert image.format == "PNG"
        assert image.size == (30, 20)
        assert not image.getexif()
        assert "private camera note" not in repr(image.info)


@pytest.mark.parametrize("value", [b"not an image", b"", b"x" * (MAX_BYTES + 1)])
def test_cover_rejects_malformed_and_oversized_input(value):
    with pytest.raises(ValidationError):
        canonical_cover(value)


def test_cover_rejects_animated_image():
    output = BytesIO()
    Image.new("RGB", (10, 10), "red").save(output, format="PNG", save_all=True,
        append_images=[Image.new("RGB", (10, 10), "blue")])
    with pytest.raises(ValidationError):
        canonical_cover(output.getvalue())

"""Synthetic evidence photos for the showcase seed.

Each photo is a flat brand-colour tile carrying the item name. It is obviously a
placeholder, not a photo of a real object. The bytes take the same path a browser
upload does: `issue_upload` writes the immutable EvidencePhoto row and presigns the
STAGING key, the bytes land on that staging key, and the workflow that consumes the
photo promotes it to the final key exactly once.
"""
import io

from django.conf import settings
from PIL import Image, ImageDraw, ImageFont

from apps.evidence import storage
from apps.evidence.models import EvidencePhoto
from apps.evidence.services_upload import issue_upload

# Space Works brand palette (docs/brand): teal, coral, sun, lime, sky.
TILE_COLOURS = ("#006E63", "#FF7447", "#FFD447", "#DFFF8F", "#B5CDFF")
INK = "#142C2A"
PAPER = "#FFF4E8"


def placeholder_jpeg(label, colour):
    image = Image.new("RGB", (800, 600), colour)
    draw = ImageDraw.Draw(image)
    try:
        font = ImageFont.load_default(size=44)
    except TypeError:  # Pillow < 10.1 has no sized default font.
        font = ImageFont.load_default()
    text_colour = PAPER if colour in ("#006E63", "#FF7447") else INK
    draw.text((48, 250), label[:28], fill=text_colour, font=font)
    draw.text((48, 530), "Showcase placeholder", fill=text_colour, font=font)
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=80)
    return buffer.getvalue()


def upload_evidence(makerspace, actor, evidence_type, label, index=0):
    """Create one evidence row and put its bytes on the staging key."""
    data = placeholder_jpeg(label, TILE_COLOURS[index % len(TILE_COLOURS)])
    photo, _ = issue_upload(
        makerspace, actor=actor, evidence_type=evidence_type,
        content_type="image/jpeg", size_bytes=len(data),
    )
    storage._client().put_object(
        Bucket=settings.AWS_STORAGE_BUCKET_NAME,
        Key=storage.staging_key(photo.object_key),
        Body=data,
        ContentType="image/jpeg",
    )
    return photo


def issue_photo(makerspace, actor, label, index=0):
    return upload_evidence(makerspace, actor, EvidencePhoto.EvidenceType.ISSUE, label, index)


def return_photo(makerspace, actor, label, index=0):
    return upload_evidence(makerspace, actor, EvidencePhoto.EvidenceType.RETURN, label, index)

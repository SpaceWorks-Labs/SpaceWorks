"""Upload design artwork: backgrounds and image layers (<= 8 MB) and watermarks (<= 5 MB).

Presign -> the browser uploads to `staging/<final>` -> finalise reads it back, sniffs
and re-encodes it server-side (metadata stripped, bounded size), writes the final key
and charges storage. The final key is never client-writable (Hard Rule).
"""
from django.utils.translation import gettext
import hashlib
import uuid

from django.db import transaction
from rest_framework.exceptions import NotFound, ValidationError

from apps.audit import services as audit

from .images import ALLOWED, normalise
from .models import CardDesignAsset
from .storage import presign_staging, put_bytes, take_staging

LIMITS = {"background": 8 * 1024 * 1024, "image": 8 * 1024 * 1024, "watermark": 5 * 1024 * 1024}
EDGES = {"background": 2400, "image": 2400, "watermark": 1200}


def presign(actor, makerspace, kind, content_type):
    if kind not in LIMITS or content_type not in ALLOWED:
        raise ValidationError({"content_type": gettext("Upload a PNG, JPEG or WebP image.")})
    asset_id = uuid.uuid4()
    row = CardDesignAsset.objects.create(asset_id=asset_id, makerspace=makerspace, kind=kind,
                                         object_key=f"card-assets/{makerspace.pk}/{asset_id.hex}",
                                         content_type=content_type, uploaded_by=actor)
    return {"asset_id": str(asset_id), **presign_staging(row.object_key, content_type, LIMITS[kind])}


def finalize(actor, makerspace, asset_id):
    from apps.tenant_migration.gate_runtime import assert_write_allowed
    assert_write_allowed(makerspace.pk)
    from apps.makerspaces.limits_usage import add_storage
    row = CardDesignAsset.objects.filter(makerspace=makerspace, asset_id=asset_id).first()
    if row is None:
        raise NotFound()
    if row.ready:
        return row
    data = take_staging(row.object_key, LIMITS[row.kind])
    if data is None:
        raise ValidationError({"asset_id": gettext("Upload not found; upload the image first.")})
    png, width, height, mean = normalise(data, max_edge=EDGES[row.kind])
    with transaction.atomic():
        row = CardDesignAsset.objects.select_for_update().get(pk=row.pk)
        add_storage(makerspace, len(png))  # charge before the write: a space at its cap leaves no orphan object
        put_bytes(row.object_key, png, "image/png")
        row.content_type, row.size_bytes, row.sha256 = "image/png", len(png), hashlib.sha256(png).hexdigest()
        row.width_px, row.height_px, row.mean_colour, row.ready = width, height, mean, True
        row.save(update_fields=["content_type", "size_bytes", "sha256", "width_px", "height_px", "mean_colour",
                                "ready"])
        if row.kind == "watermark":
            audit.record(actor, "card_design.watermark_updated", makerspace=makerspace, target=row,
                         meta={"kind": row.kind})
        else:
            audit.record(actor, "card_design.background_updated", makerspace=makerspace, target=row,
                         meta={"kind": row.kind})
    return row


def read(makerspace, asset_id):
    """Bytes for the designer canvas (staff only, same space)."""
    from .storage import read_optional
    row = CardDesignAsset.objects.filter(makerspace=makerspace, asset_id=asset_id, ready=True).first()
    if row is None:
        raise NotFound()
    data = read_optional(row.object_key)
    if data is None:
        raise NotFound()
    return data

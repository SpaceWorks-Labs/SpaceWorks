"""Template files (SPEC section 10): export a space template to JSON with its images, import one into a space.

Format `{format: "spaceworks.card-template", format_version: 1, name, description, kind, domain_hint, document, assets}`.
In the file, asset ids are `ref:<n>` and `assets` carries each image as base64 (<= 6 MB in total). Import re-creates every
image through the normal pipeline (re-encoded, storage charged, private bucket), remaps the ids and validates the
document like any save. A file from a newer format version is refused; unknown keys are refused.
"""
import base64
import binascii
import hashlib
import json
import uuid
from copy import deepcopy

from django.db import transaction
from django.utils.translation import gettext
from rest_framework.exceptions import ValidationError

from . import designs
from .images import ALLOWED, normalise
from .layout import MAX_BYTES, asset_ids
from .models import CardDesignAsset
from .storage import delete_quietly, put_bytes, read_optional
from .templates import LIMIT_KEY, _save

FORMAT = "spaceworks.card-template"
FORMAT_VERSION = 1
MAX_ASSETS = 12
MAX_TOTAL_BYTES = 6 * 1024 * 1024
KEYS = {"format", "format_version", "name", "description", "kind", "domain_hint", "document", "assets"}


def _map_ids(document, mapping):
    """Replace every asset id in a document through `mapping` (a copy)."""
    result = deepcopy(document)
    if result.get("watermark", {}).get("asset_id"):
        result["watermark"]["asset_id"] = mapping[result["watermark"]["asset_id"]]
    for side in ("front", "back"):
        background = result[side]["background"]
        if background.get("kind") == "image":
            background["asset_id"] = mapping[background["asset_id"]]
        for layer in result[side]["layers"]:
            if layer["kind"] == "image":
                layer["asset_id"] = mapping[layer["asset_id"]]
    return result


def export_file(space, row):
    ids = sorted(asset_ids(row.document))
    refs = {asset_id: f"ref:{index}" for index, asset_id in enumerate(ids, 1)}
    rows = {str(item.asset_id): item for item in CardDesignAsset.objects.filter(
        makerspace=space, asset_id__in=ids, ready=True)}
    files, total = [], 0
    for asset_id in ids:
        item = rows.get(asset_id)
        data = read_optional(item.object_key) if item else None
        if not data:
            raise ValidationError({"detail": gettext("An image in this template is missing, so it cannot be exported.")})
        total += len(data)
        if total > MAX_TOTAL_BYTES:
            raise ValidationError({"detail": gettext("This template's images are too large to export (6 MB).")})
        files.append({"ref": refs[asset_id], "kind": item.kind, "content_type": item.content_type,
                      "data_base64": base64.b64encode(data).decode("ascii")})
    return {"format": FORMAT, "format_version": FORMAT_VERSION, "name": row.name, "description": row.description,
            "kind": row.kind, "domain_hint": row.domain_hint, "document": _map_ids(row.document, refs),
            "assets": files}


def _prepare_asset(actor, space, kind, data):
    """One imported image as a ready, private design asset ROW (re-encoded; same rules as an upload).

    Nothing is written to storage here (M12): the bytes are returned and put only after the whole file
    validated and the storage charge succeeded, so a refused import leaves no object behind.
    """
    png, width, height, mean = normalise(data, max_edge=2400)
    asset_id = uuid.uuid4()
    key = f"card-assets/{space.pk}/{asset_id.hex}"
    CardDesignAsset.objects.create(asset_id=asset_id, makerspace=space, kind=kind, object_key=key,
                                   content_type="image/png", size_bytes=len(png),
                                   sha256=hashlib.sha256(png).hexdigest(), width_px=width, height_px=height,
                                   mean_colour=mean, ready=True, uploaded_by=actor)
    return str(asset_id), key, png


def _store(space, pending):
    """Charge, then write every prepared image; on any failure delete what was written and re-raise."""
    from apps.makerspaces.limits_usage import add_storage
    add_storage(space, sum(len(png) for _key, png in pending))
    written = []
    try:
        for key, png in pending:
            put_bytes(key, png, "image/png")
            written.append(key)
    except Exception:
        for key in written:
            delete_quietly(key)
        raise


def _create_asset(actor, space, kind, data):
    """Prepare and store one image at once; for a single asset made outside an import."""
    asset_id, key, png = _prepare_asset(actor, space, kind, data)
    _store(space, [(key, png)])
    return asset_id


def _check_file(value):
    if not isinstance(value, dict) or set(value) - KEYS or value.get("format") != FORMAT:
        raise ValidationError({"file": gettext("This is not a Space Works template file.")})
    version = value.get("format_version")
    if type(version) is not int or version < 1:
        raise ValidationError({"file": gettext("This template file has no valid version.")})
    if version > FORMAT_VERSION:
        raise ValidationError({"file": gettext("This template file is from a newer version of Space Works.")})
    files = value.get("assets", [])
    if not isinstance(files, list) or len(files) > MAX_ASSETS or not isinstance(value.get("document"), dict):
        raise ValidationError({"file": gettext("This template file is damaged.")})
    if len(json.dumps(value["document"], separators=(",", ":"))) > MAX_BYTES:
        raise ValidationError({"file": gettext("The design is larger than 256 KB.")})
    return files


@transaction.atomic
def import_file(actor, space, value):
    from apps.managed_hosting.extra_quotas import check_extra_quota_locked
    check_extra_quota_locked(space, LIMIT_KEY)
    files = _check_file(value)
    mapping, pending, total = {}, [], 0
    for item in files:
        if (not isinstance(item, dict) or set(item) - {"ref", "kind", "content_type", "data_base64"}
                or not isinstance(item.get("ref"), str) or item["ref"] in mapping
                or item.get("content_type") not in ALLOWED or item.get("kind") not in ("background", "image", "watermark")):
            raise ValidationError({"file": gettext("An image in this template file is not valid.")})
        try:
            data = base64.b64decode(item["data_base64"], validate=True)
        except (binascii.Error, TypeError, ValueError, KeyError):
            raise ValidationError({"file": gettext("An image in this template file is damaged.")}) from None
        total += len(data)
        if total > MAX_TOTAL_BYTES:
            raise ValidationError({"file": gettext("The images in this template file are too large (6 MB).")})
        mapping[item["ref"]], key, png = _prepare_asset(actor, space, item["kind"], data)
        pending.append((key, png))
    document = value["document"]
    try:
        document = _map_ids(document, mapping)
    except (KeyError, TypeError, AttributeError):
        raise ValidationError({"file": gettext("The design refers to an image the file does not carry.")}) from None
    clean = designs.validated(space.pk, document, check_contrast=False)
    if clean.get("source"):
        raise ValidationError({"file": gettext("Badge-designer designs are imported through the badge designer.")})
    name = value.get("name") if isinstance(value.get("name"), str) else ""
    description = value.get("description") if isinstance(value.get("description"), str) else ""
    hint = value.get("domain_hint") if value.get("domain_hint") in ("", "member_cards", "id_programme", "event_card",
                                                                   "event_ticket", "staff_cards") else ""
    row = _save(actor, space, name, description, clean, hint, None, "card_template.imported")
    # Last, after every check passed (M12): charge storage, then write the bytes. A cap refusal or a failed
    # put rolls back the rows above and leaves nothing in the bucket.
    _store(space, pending)
    return row

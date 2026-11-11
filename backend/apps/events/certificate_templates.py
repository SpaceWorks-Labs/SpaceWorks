"""Certificate design validation; templates contain layout, never recipient PII."""

from django.utils.translation import gettext
from copy import deepcopy

from rest_framework.exceptions import ValidationError

from apps.operations.printable_layout import normalize_element, number

DEFAULT_CERTIFICATE_TEMPLATE = {
    "version": 1, "page_width_mm": 297.0, "page_height_mm": 210.0, "grid_mm": 1.0,
    "name_box": {"field": "name", "x_mm": 25.0, "y_mm": 76.0,
                 "width_mm": 247.0, "height_mm": 18.0, "font": "sans",
                 "font_size_pt": 24.0, "bold": True, "align": "center", "colour": "#0F172A"},
}


def read_parameters(value, *, has_artwork=False):
    """Upgrade a design projection, while leaving stored/issued legacy bytes alone."""
    normalized = normalize_certificate_template(value)
    if normalized["version"] == 1:
        from .certificates.layout import upgrade_legacy, normalize_document
        return normalize_document(upgrade_legacy(normalized, include_labels=not has_artwork))
    return normalized


def normalize_certificate_template(value):
    if isinstance(value, dict) and value.get("version") == 2:
        from .certificates.layout import normalize_document
        return normalize_document(value)
    if not isinstance(value, dict) or set(value) - set(DEFAULT_CERTIFICATE_TEMPLATE):
        raise ValidationError({"parameters": gettext("Unknown certificate template properties.")})
    result = {**deepcopy(DEFAULT_CERTIFICATE_TEMPLATE), **value}
    if type(result["version"]) is not int or result["version"] != 1:
        raise ValidationError({"version": gettext("Use certificate template version 1.")})
    width = number(result["page_width_mm"], 100, 420, "page_width_mm")
    height = number(result["page_height_mm"], 100, 420, "page_height_mm")
    result["grid_mm"] = number(result["grid_mm"], 0.5, 10, "grid_mm")
    result["name_box"] = normalize_element(result["name_box"], width=width, height=height,
                                            fields={"name"}, grid_mm=result["grid_mm"])
    result["page_width_mm"], result["page_height_mm"] = width, height
    return result


def issuance_layout(revision):
    if revision is None:
        result = read_parameters({})
        return _verification_slots(result)
    result = deepcopy(revision.parameters)
    artwork = revision.artwork
    legacy_background = result.get("version") == 1 and artwork is not None
    if result.get("version") == 1:
        result = read_parameters(result, has_artwork=legacy_background)
        result["legacy_background"] = legacy_background
    result = _verification_slots(result)
    if result.get("version") == 2:
        from .models_certificate_templates import EventCertificateArtwork
        ids = [layer["resource_id"] for layer in result["layers"] if layer["type"] == "image"]
        rows = EventCertificateArtwork.objects.filter(event_id=revision.event_id, resource_id__in=ids,
                                                     promoted_at__isnull=False)
        resources = {str(row.resource_id): {"key": row.object_key, "version": row.version_id,
                                            "sha256": row.sha256} for row in rows}
        if set(ids) != set(resources):
            raise ValidationError({"layers": gettext("Every image must be promoted artwork owned by this event.")})
        result["artwork_resources"] = resources
    result.update(artwork_object_key=artwork.object_key if artwork else "",
                  artwork_version_id=artwork.version_id if artwork else "",
                  artwork_sha256=artwork.sha256 if artwork else "")
    return result


def _verification_slots(result):
    """Every newly issued certificate has its public ID and typed verification QR."""
    from uuid import uuid5, NAMESPACE_URL
    width, height = result["page_width_mm"], result["page_height_mm"]
    types = {layer["type"] for layer in result["layers"]}
    for kind, box in (("certificate_qr", (8, height-33, 25, 25)),
                      ("certificate_id", (40, height-12, width-48, 8))):
        if kind in types:
            continue
        if len(result["layers"]) >= 20:
            raise ValidationError({"layers": gettext("Reserve layers for the certificate ID and verification QR.")})
        x, y, w, h = box
        layer = {"id": str(uuid5(NAMESPACE_URL, f"spaceworks:certificate:{kind}")),
                 "order": len(result["layers"]), "type": kind, "x_mm": x, "y_mm": y,
                 "width_mm": w, "height_mm": h, "rotation": 0}
        if kind == "certificate_qr":
            layer["resource_slot"] = "certificate_verification_qr"
        else:
            layer.update(font_family="Outfit", font_weight=400, font_size_pt=7, align="right", shrink_to_fit=True)
        result["layers"].append(layer)
    from .certificates.layout import normalize_document
    normalized = normalize_document({key: result[key] for key in ("version", "page_width_mm", "page_height_mm", "layers")})
    result["layers"] = normalized["layers"]
    return result

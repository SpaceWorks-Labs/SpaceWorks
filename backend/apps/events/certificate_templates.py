"""Certificate design validation; templates contain layout, never recipient PII."""

from copy import deepcopy

from rest_framework.exceptions import ValidationError

from apps.operations.printable_layout import normalize_element, number

DEFAULT_CERTIFICATE_TEMPLATE = {
    "version": 1, "page_width_mm": 297.0, "page_height_mm": 210.0, "grid_mm": 1.0,
    "name_box": {"field": "name", "x_mm": 25.0, "y_mm": 76.0,
                 "width_mm": 247.0, "height_mm": 18.0, "font": "sans",
                 "font_size_pt": 24.0, "bold": True, "align": "center", "colour": "#0F172A"},
}


def normalize_certificate_template(value):
    if not isinstance(value, dict) or set(value) - set(DEFAULT_CERTIFICATE_TEMPLATE):
        raise ValidationError({"parameters": "Unknown certificate template properties."})
    result = {**deepcopy(DEFAULT_CERTIFICATE_TEMPLATE), **value}
    if type(result["version"]) is not int or result["version"] != 1:
        raise ValidationError({"version": "Use certificate template version 1."})
    width = number(result["page_width_mm"], 100, 420, "page_width_mm")
    height = number(result["page_height_mm"], 100, 420, "page_height_mm")
    result["grid_mm"] = number(result["grid_mm"], 0.5, 10, "grid_mm")
    result["name_box"] = normalize_element(result["name_box"], width=width, height=height,
                                            fields={"name"}, grid_mm=result["grid_mm"])
    result["page_width_mm"], result["page_height_mm"] = width, height
    return result


def issuance_layout(revision):
    if revision is None:
        return deepcopy(DEFAULT_CERTIFICATE_TEMPLATE)
    result = deepcopy(revision.parameters)
    artwork = revision.artwork
    result.update(artwork_object_key=artwork.object_key if artwork else "",
                  artwork_version_id=artwork.version_id if artwork else "",
                  artwork_sha256=artwork.sha256 if artwork else "")
    return result

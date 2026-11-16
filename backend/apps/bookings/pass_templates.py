"""Booking-only, answer-free layout adapter over core print geometry."""
from django.utils.translation import gettext
from copy import deepcopy

from rest_framework.exceptions import ValidationError

from apps.operations.printable_layout import normalize_elements, number, page_layout

PASS_FIELDS = ("name", "resource", "booking_window", "reference")
DEFAULT_PASS_TEMPLATE = {
    "version": 2, "paper_size": "A4", "orientation": "portrait",
    "page_width_mm": None, "page_height_mm": None,
    "card_width_mm": 90.0, "card_height_mm": 60.0,
    "margin_mm": 10.0, "gap_mm": 5.0, "grid_mm": 1.0,
    "elements": [
        {"field": field, "x_mm": 4, "y_mm": y, "width_mm": 82,
         "height_mm": height, "font_size_pt": size, "font": "sans",
         "bold": field == "name", "align": "left", "colour": "#0F172A"}
        for field, y, height, size in (
            ("name", 4, 12, 18), ("resource", 18, 10, 12),
            ("booking_window", 30, 16, 10), ("reference", 48, 8, 9),
        )
    ],
}


def normalize_pass_template(value):
    # The same policy applies to writes AND stored/legacy reads; never silently
    # strip a forbidden answer binding and accidentally authorize that template.
    if value is None or value == {}:
        value = deepcopy(DEFAULT_PASS_TEMPLATE)
    if not isinstance(value, dict) or set(value) - set(DEFAULT_PASS_TEMPLATE):
        raise ValidationError({"template": gettext("Unknown booking pass template properties.")})
    template = {**deepcopy(DEFAULT_PASS_TEMPLATE), **value}
    if type(template["version"]) is not int or template["version"] != 2:
        raise ValidationError({"version": gettext("Use booking pass version 2.")})
    if template["paper_size"] not in ("A4", "LETTER", "custom"):
        raise ValidationError({"paper_size": gettext("Use A4, LETTER or custom.")})
    if template["orientation"] not in ("portrait", "landscape"):
        raise ValidationError({"orientation": gettext("Use portrait or landscape.")})
    for key, bounds in {
        "card_width_mm": (40, 150), "card_height_mm": (30, 120),
        "margin_mm": (0, 40), "gap_mm": (0, 30), "grid_mm": (0.5, 10),
    }.items():
        template[key] = number(template[key], *bounds, key)
    for key in ("page_width_mm", "page_height_mm"):
        if template["paper_size"] == "custom":
            template[key] = number(template[key], 100, 500, key)
        else:
            template[key] = None
    template["elements"] = normalize_elements(
        template["elements"], width=template["card_width_mm"],
        height=template["card_height_mm"], fields=PASS_FIELDS,
        grid_mm=template["grid_mm"],
    )
    page_layout(template)
    return template

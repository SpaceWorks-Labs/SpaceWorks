from django.utils.translation import gettext
from rest_framework import serializers
from apps.operations.printable_layout import normalize_elements, page_layout, number


DEFAULT_BADGE_TEMPLATE = {
    "version": 2,
    "paper_size": "A4",
    "orientation": "portrait",
    "page_width_mm": None,
    "page_height_mm": None,
    "card_width_mm": 90.0,
    "card_height_mm": 55.0,
    "margin_mm": 10.0,
    "gap_mm": 5.0,
    "template": "standard",
    "fields": ["name", "event_title", "date_time", "location", "registration_number"],
    "font_size_pt": 9,
    "name_font_size_pt": 15,
    "text_align": "left",
    "include_qr": False,
    "grid_mm": 1.0,
    "elements": [],
}
SAFE_FIELDS = frozenset({
    "name", "event_title", "date_time", "location", "registration_number",
    # Release 2 (#128 C-36): the crew chip; blank for participants and while `events.crew` is off.
    "crew_role",
})
SENSITIVE_FIELDS = frozenset({"email", "phone"})
MAX_BADGES = 200
MAX_PAGES = 50
MAX_TEXT_LENGTH = 500


def _custom_ids(event):
    return {str(question["id"]) for question in (event.custom_form or [])}


def normalize_badge_template(value, event):
    if value in (None, {}):
        value = DEFAULT_BADGE_TEMPLATE
    if not isinstance(value, dict):
        raise serializers.ValidationError({"badge_template": gettext("Expected an object.")})
    unknown = set(value) - set(DEFAULT_BADGE_TEMPLATE)
    if unknown:
        raise serializers.ValidationError({key: "Unknown template field." for key in unknown})
    template = {**DEFAULT_BADGE_TEMPLATE, **value}
    if type(template["version"]) is not int or template["version"] not in (1, 2):
        raise serializers.ValidationError({"version": gettext("Use badge template version 1 or 2.")})
    if type(template["include_qr"]) is not bool:
        raise serializers.ValidationError({"include_qr": gettext("Expected a boolean.")})
    legacy_version = template["version"] == 1
    legacy = legacy_version or not value.get("elements")
    template["version"] = 2
    template["include_qr"] = False
    if template["paper_size"] not in {"A4", "LETTER", "custom"}:
        raise serializers.ValidationError({"paper_size": gettext("Use A4, LETTER, or custom.")})
    if template["orientation"] not in {"portrait", "landscape"}:
        raise serializers.ValidationError({"orientation": gettext("Use portrait or landscape.")})
    if template["template"] != "standard":
        raise serializers.ValidationError({"template": gettext("Unknown badge template.")})
    if template["text_align"] not in {"left", "center"}:
        raise serializers.ValidationError({"text_align": gettext("Use left or center.")})
    numeric_bounds = {
        "card_width_mm": (40, 150), "card_height_mm": (30, 120),
        "margin_mm": (0, 40), "gap_mm": (0, 30),
        "font_size_pt": (6, 48), "name_font_size_pt": (6, 48),
    }
    if template["paper_size"] == "custom":
        numeric_bounds.update({"page_width_mm": (100, 500), "page_height_mm": (100, 500)})
    for field, (minimum, maximum) in numeric_bounds.items():
        template[field] = number(template[field], minimum, maximum, field)
    fields = template["fields"]
    if not isinstance(fields, list) or not fields or len(fields) > 12:
        raise serializers.ValidationError({"fields": gettext("Choose between 1 and 12 fields.")})
    if any(not isinstance(item, str) for item in fields) or len(fields) != len(set(fields)):
        raise serializers.ValidationError({"fields": gettext("Field selectors must be unique strings.")})
    custom_ids = _custom_ids(event)
    invalid = [item for item in fields if (
        item not in SAFE_FIELDS | SENSITIVE_FIELDS
        and not (item.startswith("custom:") and item[7:] in custom_ids)
    )]
    if invalid:
        raise serializers.ValidationError({"fields": gettext('Unknown selectors: {value}.').format(value=', '.join(invalid))})
    if legacy_version:
        fields = [field for field in fields if field not in SENSITIVE_FIELDS] or ["name"]
    if set(fields) & SENSITIVE_FIELDS:
        raise serializers.ValidationError({"fields": gettext("Email and phone must never appear on printed badges.")})
    page_layout(template)
    template["fields"] = fields
    if legacy:
        template["elements"] = positioned_fields(template)
    template["elements"] = normalize_elements(
        template["elements"], width=template["card_width_mm"], height=template["card_height_mm"],
        fields=set(fields), grid_mm=template["grid_mm"],
    )
    if {element["field"] for element in template["elements"]} != set(fields):
        raise serializers.ValidationError({"elements": gettext("Each selected field needs one positioned element.")})
    return template


def positioned_fields(template):
    """Convert v1's ordered fields on read, leaving stored legacy JSON intact."""
    height = (template["card_height_mm"] - 6) / len(template["fields"])
    return [{"field": field, "x_mm": 3, "y_mm": 3 + index * height,
             "width_mm": template["card_width_mm"] - 6, "height_mm": height,
             "font_size_pt": template["name_font_size_pt"] if field == "name" else template["font_size_pt"],
             "bold": field == "name", "align": template["text_align"], "font": "sans",
             "colour": "#0F172A"} for index, field in enumerate(template["fields"])]

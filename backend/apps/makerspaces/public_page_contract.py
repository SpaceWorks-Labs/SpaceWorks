"""Versioned, model-free editorial document contract. Derived facts never enter it."""

import json
import uuid
import unicodedata
from collections import Counter
from rest_framework import serializers as s
from drf_spectacular.utils import extend_schema_field, PolymorphicProxySerializer
from .public_page_sections import PAYLOADS, StrictSerializer

MAX_DOCUMENT_BYTES = 131072
PALETTES = {"maker_teal": "#006E63", "workshop_orange": "#FF7447", "citron": "#DFFF8F",
            "sky_blue": "#B5CDFF", "warm_yellow": "#FFD447"}
BASE_TYPES = ("about", "gallery", "team", "testimonials", "links")
REQUIRED = {"makerspace": ("functional_content",),
            "organization": ("linked_makerspaces", "organization_events"), "event": ()}
SECTION_TYPES = {"makerspace": (*BASE_TYPES, "upcoming_events", "stats", "location", "functional_content",
                                "membership_plans"),
                 "organization": (*BASE_TYPES, "location", "linked_makerspaces", "organization_events"),
                 "event": BASE_TYPES}
# Stable required-group identity across virtual GETs and first save.
GROUP_NAMESPACE = uuid.UUID("b3fa19d5-784c-4324-9e45-8c54b0bf9af5")


def empty_document(kind):
    return {"schema_version": 1, "cover_mode": "inherit", "cover_asset_id": None,
            "accent_choice": "inherit", "sections": [
                {"id": str(uuid.uuid5(GROUP_NAMESPACE, f"{kind}:{key}")), "type": key,
                 "enabled": True, "payload": {} if key == "functional_content" else {"title": ""}}
                for key in REQUIRED[kind]]}


class Section(StrictSerializer):
    id = s.UUIDField()
    type = s.ChoiceField(choices=tuple(PAYLOADS))
    enabled = s.BooleanField()
    payload = s.JSONField()


# Documentation uses the same payload registry as validation, so adding a reviewed
# section cannot silently leave its OpenAPI body as an untyped JSON object.
INPUT_SECTION_TYPES = {key: type(f"PublicPage{key.title().replace('_', '')}SectionInput", (Section,), {
        "type": s.ChoiceField(choices=(key,)), "payload": serializer(),
    }) for key, serializer in PAYLOADS.items()
}
SECTION_SCHEMA = PolymorphicProxySerializer(component_name="PublicPageSectionInput",
    serializers=INPUT_SECTION_TYPES, resource_type_field_name="type", many=True)


@extend_schema_field(SECTION_SCHEMA)
class SectionsField(s.ListField):
    def __init__(self, **kwargs):
        super().__init__(child=Section(), max_length=20, **kwargs)


class Document(StrictSerializer):
    schema_version = s.IntegerField(min_value=1, max_value=1)
    cover_mode = s.ChoiceField(choices=("inherit", "asset", "none"))
    cover_asset_id = s.IntegerField(min_value=1, allow_null=True)
    accent_choice = s.ChoiceField(choices=("inherit", *PALETTES), allow_null=True)
    sections = SectionsField()


def normalize_document(value, *, kind, previous=None):
    serializer = Document(data=value)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data
    data["accent_choice"] = data["accent_choice"] or "inherit"
    if (data["cover_mode"] == "asset") != (data["cover_asset_id"] is not None):
        raise s.ValidationError({"cover_asset_id": "Only asset cover mode requires an image."})
    counts, ids = Counter(), set()
    for section in data["sections"]:
        key = section["type"]
        if key not in SECTION_TYPES[kind]:
            raise s.ValidationError({"sections": f"Unsupported section for {kind}: {key}."})
        if section["id"] in ids:
            raise s.ValidationError({"sections": "Section IDs must be unique."})
        ids.add(section["id"])
        counts[key] += 1
        if counts[key] > (2 if key == "about" else 1):
            raise s.ValidationError({"sections": f"Too many {key} sections."})
        payload = PAYLOADS[key](data=section["payload"])
        payload.is_valid(raise_exception=True)
        section["payload"] = payload.validated_data
        rows = section["payload"].get("entries", [])
        row_ids = [row["id"] for row in rows]
        if len(row_ids) != len(set(row_ids)):
            raise s.ValidationError({"sections": "Entry IDs must be unique within a section."})
        if key == "location" and kind != "makerspace" and section["payload"]["source"] != "entered":
            raise s.ValidationError({"sections": "This owner requires an explicitly entered location."})
    for key in REQUIRED[kind]:
        group = next((row for row in data["sections"] if row["type"] == key), None)
        if group is None or not group["enabled"]:
            raise s.ValidationError({"sections": f"The {key} group is required and enabled."})
        old = next((row for row in (previous or empty_document(kind))["sections"] if row["type"] == key), None)
        if old and str(group["id"]) != str(old["id"]):
            raise s.ValidationError({"sections": "Required group identity cannot change."})
    validate_text_tree(data)
    encoded = json.dumps(data, ensure_ascii=False, separators=(",", ":"), default=str)
    if len(encoded.encode("utf-8")) > MAX_DOCUMENT_BYTES:
        from .public_page_errors import PagePayloadTooLarge
        raise PagePayloadTooLarge("Document exceeds 131072 UTF-8 bytes.")
    return json.loads(encoded)


def validate_text_tree(value):
    if isinstance(value, str) and any(unicodedata.category(char) in {"Cs", "Cc"} and char not in "\n\t" for char in value):
        raise s.ValidationError({"document": "Text contains unsupported control or surrogate characters."})
    if isinstance(value, dict):
        for child in value.values():
            validate_text_tree(child)
    elif isinstance(value, list):
        for child in value:
            validate_text_tree(child)


def reference_slots(document):
    """Exact semantic paths; never recursively interpret arbitrary authored strings."""
    assets, members = {}, {}
    if document.get("cover_asset_id") is not None:
        assets["cover"] = document["cover_asset_id"]
    for section in document["sections"]:
        payload = section["payload"]
        if section["type"] == "gallery":
            for index, item in enumerate(payload["items"]):
                assets[f"{section['id']}:{index}"] = item["asset_id"]
        elif section["type"] == "team":
            for item in payload["entries"]:
                if item["kind"] == "member":
                    members[str(item["id"])] = item["profile_id"]
    return assets, members


def validate_stored_document(value, *, kind):
    from copy import deepcopy
    document = deepcopy(value)
    for section in document.get("sections", []):
        if section.get("type") == "team":
            for row in section["payload"]["entries"]:
                if row["kind"] == "member":
                    if row.get("member_slot_id") != row["id"] or "profile_id" in row:
                        raise s.ValidationError({"document": "Stored member entries require a stable typed reference slot."})
                    row.pop("member_slot_id")
                    row["profile_id"] = 1  # Schema validation only; typed rows own the real identity.
    normalize_document(document, kind=kind)
    return value

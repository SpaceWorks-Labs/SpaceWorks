"""Reviewed snapshot delta on the Django-free host; live spectacular remains a gate."""
from copy import deepcopy
import json
from pathlib import Path

PATH = Path(__file__).resolve().parents[3] / "frontend/openapi-schema.json"
schema = json.loads(PATH.read_text(encoding="utf-8"))
components, paths = schema["components"]["schemas"], schema["paths"]


def boolean(component, field):
    components[component]["properties"][field] = {"type": "boolean", "readOnly": True}
    components[component]["required"] = sorted(set(components[component].get("required", [])) | {field})


boolean("BookableSpaceAdmin", "passes_enabled")
boolean("BookingArrival", "can_print_pass")
boolean("BookingConfirmation", "pass_available")
element = deepcopy(components["PositionedElement"])
element["additionalProperties"] = False
element["properties"]["field"] = {"type": "string", "enum": ["name", "resource", "booking_window", "reference"]}
components["BookingPassElement"] = element
components["BookingPassTemplate"] = {
    "type": "object", "additionalProperties": False,
    "description": "Version 2 answer-free booking layout. Never accepts contacts, custom answers, notes, artwork, QR or arbitrary text. Defaults apply to omitted properties.",
    "properties": {
        "version": {"type": "integer", "minimum": 2, "maximum": 2},
        "paper_size": {"type": "string", "enum": ["A4", "LETTER", "custom"]},
        "orientation": {"type": "string", "enum": ["portrait", "landscape"]},
        **{key: {"type": "number", "format": "double", "minimum": minimum, "maximum": maximum,
                 **({"nullable": True} if key.startswith("page_") else {})}
           for key, minimum, maximum in (
               ("page_width_mm", 100, 500), ("page_height_mm", 100, 500),
               ("card_width_mm", 40, 150), ("card_height_mm", 30, 120),
               ("margin_mm", 0, 40), ("gap_mm", 0, 30), ("grid_mm", 0.5, 10),
           )},
        "elements": {"type": "array", "minItems": 1, "maxItems": 4,
                     "items": {"$ref": "#/components/schemas/BookingPassElement"}},
    },
}
staff_base = paths["/api/v1/admin/spaces/{id}/arrival/{booking_id}/reverse/"]["post"]
member_base = paths["/api/v1/public/{makerspace_slug}/my-bookings/{public_token}/confirmation/"]["get"]


def operation(base, operation_id, description, *, pdf=False, template=False, empty=False, resource=False):
    result = deepcopy(base)
    result.update(operationId=operation_id, description=description)
    if resource:
        result["parameters"] = [p for p in result["parameters"] if p["name"] != "booking_id"]
    result.pop("requestBody", None)
    if template:
        result["requestBody"] = {"content": {"application/json": {"schema": {
            "$ref": "#/components/schemas/BookingPassTemplate"}}}, "required": True}
    elif empty:
        result["requestBody"] = {"content": {"application/json": {"schema": {
            "type": "object", "additionalProperties": False}}}, "required": True}
    result["responses"]["200"] = {"description": "Private/no-store, no-referrer. Audited PDF rendering at 30/hour/account." if pdf else "Validated answer-free template.",
        "content": {"application/pdf" if pdf else "application/json": {"schema":
            {"type": "string", "format": "binary"} if pdf else {"$ref": "#/components/schemas/BookingPassTemplate"}}}}
    result["responses"]["403"]["description"] = "Active account with booking ownership or the required resource permission. Claim sessions refused."
    result["responses"]["404"]["description"] = "Feature/module disabled, target unavailable or foreign booking."
    return result


paths["/api/v1/admin/spaces/{id}/pass-template/"] = {
    "get": operation(staff_base, "admin_spaces_pass_template_retrieve", "Live edit_details and bookings.passes required. Stored templates revalidated on every read.", resource=True),
    "put": operation(staff_base, "admin_spaces_pass_template_update", "Save bounded answer-free layout. Requires live edit_details and bookings.passes; audits identifiers only.", template=True, resource=True),
}
paths["/api/v1/admin/spaces/{id}/pass-preview/"] = {"post": operation(staff_base,
    "admin_spaces_pass_preview_create", "Requires edit_details and bookings.passes. Fixed sample recipient, never a real booking, no answer/contact/note/credential binding.", pdf=True, template=True, resource=True)}
paths["/api/v1/admin/spaces/{id}/arrival/{booking_id}/pass/"] = {"post": operation(staff_base,
    "admin_spaces_arrival_pass_create", "Requires check_in and bookings.checkin/passes; confirmed/completed booking with current active arrival under resource then booking locks. Rebuilds answer-free PDF; template overrides refused.", pdf=True, empty=True)}
paths["/api/v1/public/{makerspace_slug}/my-bookings/{public_token}/pass.pdf"] = {"get": operation(member_base,
    "public_my_bookings_pass_retrieve", "Authenticated owner only, bookings.passes required. Confirmed/completed reservations. No membership/events/presence/payment-rail dependency. Never prints contacts, notes, custom answers or credentials.", pdf=True)}
PATH.write_text(json.dumps(schema, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
print("BK-G: four routes / five operations and typed template, confirmation and scanner projections.")

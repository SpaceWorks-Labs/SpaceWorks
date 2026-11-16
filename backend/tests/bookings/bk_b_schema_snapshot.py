"""Update the reviewed BK-B schema delta on this Django-free host.

A supported-host checkpoint must compare spectacular's live output as well.
"""
from copy import deepcopy
import json
from pathlib import Path

PATH = Path(__file__).resolve().parents[3] / "frontend/openapi-schema.json"
schema = json.loads(PATH.read_text(encoding="utf-8"))
components, paths = schema["components"]["schemas"], schema["paths"]
for name in ("clone_enabled", "staff_tools_enabled", "can_copy_booking_rules"):
    component = components["BookableSpaceAdmin"]
    component["properties"][name] = {"type": "boolean", "readOnly": True}
    component["required"] = sorted(set(component.get("required", [])) | {name})
for name, spec in {
    "cancelled_at": {"type": "string", "format": "date-time", "nullable": True, "readOnly": True},
    "status_before_cancel": {"type": "string", "readOnly": True},
    "restore_until": {"type": "string", "format": "date-time", "nullable": True, "readOnly": True},
}.items():
    components["BookingAdmin"]["properties"][name] = spec
    components["BookingAdmin"]["required"] = sorted(set(components["BookingAdmin"].get("required", [])) | {name})
components["BookingCloneInput"] = {"type": "object", "properties": {
    "copy_booking_rules": {"type": "boolean", "default": False},
}}
components["PatchedBookingDetailsInput"] = {"type": "object", "properties": {
    "note": {"type": "string", "maxLength": 5000}, "custom_answers": {"nullable": True},
}}
components["BookingTimeInput"] = {"type": "object", "properties": {
    name: {"type": "string", "format": "date-time"} for name in ("starts_at", "ends_at")
}, "required": ["ends_at", "starts_at"]}
base = paths["/api/v1/admin/bookings/{id}/cancel/"]["post"]
operations = (
    ("spaces", "clone", "post", "BookingCloneInput", "BookableSpaceAdmin", "201",
     "Clone a resource into a private copy",
     "Requires tenant MANAGE_BOOKINGS and bookings.clone. Copying booking rules needs no further action."),
    ("bookings", "details", "patch", "PatchedBookingDetailsInput", "BookingAdmin", "200",
     "Edit private reservation note or answers",
     "Requires resource manage_reservations and bookings.staff_tools. Unknown fields are refused; answers use the current schema."),
    ("bookings", "time", "post", "BookingTimeInput", "BookingAdmin", "200",
     "Move a pending or confirmed reservation",
     "Requires resource manage_reservations and bookings.staff_tools. Both old and proposed windows must be beyond the cutoff; ordinary admission rules apply. Identity, status and flat charge are preserved."),
    ("bookings", "restore", "post", None, "BookingAdmin", "200",
     "Undo a recent cancellation without money movement",
     "Requires resource manage_reservations and bookings.staff_tools. Within five minutes, restore the exact pending/confirmed state under current admission. Any historical or newly required charge refuses undo."),
)
for resource, action, method, input_name, output_name, status, summary, description in operations:
    operation = deepcopy(base)
    operation.update(operationId=f"api_v1_admin_{resource}_{action}_" + ("partial_update" if method == "patch" else "create"),
                     summary=summary, description=description)
    operation["responses"].pop("200")
    operation["responses"][status] = {"content": {"application/json": {"schema": {
        "$ref": "#/components/schemas/" + output_name}}}, "description": ""}
    for code, detail in (("429", "Too many requests."), *(([("503", "Service unavailable.")]) if action == "clone" else [])):
        operation["responses"][code] = {"content": {"application/json": {"schema": {
            "$ref": "#/components/schemas/HardwareRequestError"}}}, "description": detail}
    operation.pop("requestBody", None)
    if input_name:
        operation["requestBody"] = {"content": {mime: {"schema": {"$ref": "#/components/schemas/" + input_name}}
            for mime in ("application/json", "application/x-www-form-urlencoded", "multipart/form-data")}}
        if action == "time":
            operation["requestBody"]["required"] = True
    paths[f"/api/v1/admin/{resource}/{{id}}/{action}/"] = {method: operation}
# Registry event vocabulary follows the live catalog wherever enum schemas use it.
for name, component in components.items():
    values = component.get("enum")
    if values and all(value in values for value in ("created", "confirmed", "cancelled", "no_show")):
        if "restored" not in values:
            values.append("restored")
PATH.write_text(json.dumps(schema, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
print("Applied four BK-B routes, resource feature flags and cancellation projections.")

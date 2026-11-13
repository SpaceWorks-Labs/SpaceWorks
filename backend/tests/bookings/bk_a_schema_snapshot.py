"""Apply the BK-A contract to the checked-in schema on this Django-free host.

The Docker checkpoint must compare against spectacular's live schema too.
"""
from copy import deepcopy
import json
from pathlib import Path

PATH = Path(__file__).resolve().parents[3] / "frontend/openapi-schema.json"
schema = json.loads(PATH.read_text(encoding="utf-8"))
components, paths = schema["components"]["schemas"], schema["paths"]
permissions = ["edit_details", "manage_reservations", "check_in", "publish_page"]
names = ["StaffGrant", "StaffGrantInvite", "StaffGrantInviteCreated", "StaffGrantInviteInput",
         "StaffGrantInviteList", "StaffGrantList", "StaffGrantPermissions", "StaffGrantRedeem",
         "PatchedStaffGrantPermissions"]
mapping = {name: ("PatchedBookingStaffGrantPermissions" if name.startswith("Patched") else "Booking" + name)
           for name in names}


def remap(value):
    if isinstance(value, list):
        return [remap(item) for item in value]
    if isinstance(value, dict):
        result = {key: remap(item) for key, item in value.items()}
        if "$ref" in result:
            old = result["$ref"].rsplit("/", 1)[-1]
            if old in mapping:
                result["$ref"] = "#/components/schemas/" + mapping[old]
        if result.get("enum") == ["edit_details", "manage_registrations", "manage_invitations", "check_in", "publish_schedule"]:
            result["enum"] = permissions
        if result.get("maxItems") == 5:
            result["maxItems"] = 4
        return result
    return value


for old, new in mapping.items():
    component = remap(deepcopy(components[old]))
    props = component.get("properties", {})
    if "event" in props:
        del props["event"], props["series"]
        props["space"] = {"type": "integer", "readOnly": True}
        component["required"] = sorted(set(component.get("required", [])) - {"event", "series"} | {"space"})
    components[new] = component

components["GrantedBookingEntry"] = {
    "type": "object", "properties": {
        "space_id": {"type": "integer"}, "makerspace_id": {"type": "integer"},
        "makerspace_slug": {"type": "string"}, "name": {"type": "string"},
        "source": {"type": "string", "enum": ["booking_grant"]},
        "permissions": {"type": "array", "items": {"type": "string", "enum": permissions}},
    }, "required": ["space_id", "makerspace_id", "makerspace_slug", "name", "source", "permissions"],
}
components["AuthUserPayload"]["properties"]["booking_grants"] = {
    "type": "array", "items": {"$ref": "#/components/schemas/GrantedBookingEntry"},
}
for field, value in {
    "staff_permissions": {"type": "array", "items": {"type": "string"}, "readOnly": True},
    "can_manage_grants": {"type": "boolean", "readOnly": True},
    "staff_grants_enabled": {"type": "boolean", "readOnly": True},
    "recurring_enabled": {"type": "boolean", "readOnly": True},
}.items():
    components["BookableSpaceAdmin"]["properties"][field] = value
    components["BookableSpaceAdmin"]["required"] = sorted(set(components["BookableSpaceAdmin"]["required"]) | {field})

route_mapping = {
    "/api/v1/admin/events/{id}/staff-grants/": "/api/v1/admin/spaces/{id}/staff-grants/",
    "/api/v1/admin/events/{id}/staff-invites/": "/api/v1/admin/spaces/{id}/staff-invites/",
    "/api/v1/admin/event-staff-grants/{id}/": "/api/v1/admin/booking-staff-grants/{id}/",
    "/api/v1/admin/event-staff-grants/{id}/revoke/": "/api/v1/admin/booking-staff-grants/{id}/revoke/",
    "/api/v1/admin/event-staff-invites/{id}/revoke/": "/api/v1/admin/booking-staff-invites/{id}/revoke/",
    "/api/v1/admin/event-staff-invites/redeem/": "/api/v1/admin/booking-staff-invites/redeem/",
    "/api/v1/admin/accessible-events/": "/api/v1/admin/accessible-booking-spaces/",
}
for old, new in route_mapping.items():
    operations = remap(deepcopy(paths[old]))
    for method, operation in operations.items():
        operation["operationId"] = operation["operationId"].replace("event_staff", "booking_staff").replace("events_staff", "spaces_staff").replace("accessible_events", "accessible_booking_spaces")
        operation["tags"] = ["Bookings" if "redeem" in new else "Admin bookings"]
        operation["description"] = (
            "Requires current tenant MANAGE_BOOKINGS (local custom roles and organization actions count); "
            "resource grants cannot delegate. bookings.staff_grants must be enabled. "
            "Invites expire after seven days; redemption checks current sender authority, verified email "
            "binding, tenant origin, revocation and single use under resource and invite locks. Tokens are shown once."
        )
        if "accessible-booking" not in new:
            operation["responses"]["400"] = {"description": "Field validation, module or feature disabled.",
                "content": {"application/json": {"schema": {"type": "object", "additionalProperties": {}}}}}
        if "redeem" in new:
            operation["description"] = "Authenticated active accounts may redeem once without existing staff authority. Matching verified email, selected origin/tenant, seven-day expiry and current sender authority are checked under locks. Rate limited to 10/min/account; private/no-store."
        if "accessible-booking" in new:
            operation["responses"]["200"]["content"]["application/json"]["schema"]["$ref"] = "#/components/schemas/BookableSpaceListResponse"
            operation["description"] = "Lists only currently authorized resources, scoped to staff origin and optional makerspace_id. Grants never add tenant actions or general member access."
            operation["parameters"] = [p for p in operation.get("parameters", []) if p["name"] != "page_size"]
    paths[new] = operations

for route, operations in paths.items():
    if "/admin/spaces/" not in route and "/admin/bookings/" not in route:
        continue
    for method, operation in operations.items():
        if not isinstance(operation, dict) or "operationId" not in operation:
            continue
        note = "Booking staff authority is checked live through booking_authority. Roster, eligible-member selection, ordinary staff creation, recurrence and lifecycle actions require manage_reservations or tenant MANAGE_BOOKINGS. Descriptive fields and images require edit_details or tenant management. Resource grants never confer pricing, rule, machine, privacy/activation or finance authority. Rules retain MANAGE_MAKERSPACE."
        if note not in operation.get("description", ""):
            operation["description"] = operation.get("description", "") + " " + note

PATH.write_text(json.dumps(schema, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
print(f"BK-A schema: {len(route_mapping)} new paths, concrete grant components and auth/resource projections")

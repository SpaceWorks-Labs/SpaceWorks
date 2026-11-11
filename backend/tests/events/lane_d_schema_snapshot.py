"""Update the checked-in contract without Django; spectacular remains the integration gate."""
from copy import deepcopy
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
path = ROOT / "frontend/openapi-schema.json"
schema = json.loads(path.read_text(encoding="utf-8"))
components = schema["components"]["schemas"]
paths = schema["paths"]


def ref(name):
    return {"$ref": f"#/components/schemas/{name}"}


def obj(properties, required=None):
    return {"type": "object", "properties": deepcopy(properties), "required": required or sorted(properties)}


def json_response(name):
    return {"content": {"application/json": {"schema": ref(name)}}, "description": ""}


text = {"type": "string"}
integer = {"type": "integer"}
date = {"type": "string", "format": "date-time"}
components["EventBroadcastInput"] = obj({
    "subject": {**text, "maxLength": 200}, "body": {**text, "maxLength": 10000},
    "statuses": {"type": "array", "minItems": 1, "maxItems": 6, "default": ["registered", "attended"],
                 "items": {"type": "string", "enum": ["pending_approval", "registered", "waitlisted", "rejected", "cancelled", "attended"]}},
    "attendance": {**text, "enum": ["any", "attended", "not_attended"], "default": "any"},
}, ["body", "subject"])
components["EventBroadcast"] = obj({"id": integer, "event": integer,
    **{k: v for k, v in components["EventBroadcastInput"]["properties"].items()},
    "status": {**text, "enum": ["draft", "queued", "sending", "sent", "cancelled", "failed"]},
    "created_at": date, "queued_at": {**date, "nullable": True}, "completed_at": {**date, "nullable": True}})
for field in components["EventBroadcast"]["properties"].values():
    field["readOnly"] = True
components["EventBroadcastList"] = deepcopy(components["InviteList"])
components["EventBroadcastList"]["properties"]["results"]["items"] = ref("EventBroadcast")
components["BulkInviteInput"] = obj({"emails": {"type": "array", "minItems": 1, "maxItems": 200,
    "items": {"type": "string", "format": "email"}}, "expires_at": {**date, "nullable": True},
    "send_email": {"type": "boolean", "default": True}}, ["emails"])
components["BulkInviteResult"] = obj({"created": integer})

base = paths["/api/v1/admin/events/{id}/invites/"]
route = "/api/v1/admin/events/{id}/broadcasts/"
paths[route] = deepcopy(base)
for method, output, code in (("get", "EventBroadcastList", "200"), ("post", "EventBroadcast", "201")):
    operation = paths[route][method]
    operation["operationId"] = f"api_v1_admin_events_broadcasts_{'list' if method == 'get' else 'create'}"
    operation["description"] = "Requires live manage_registrations authority and events.broadcasts, notifications and email. Campaigns send only to eligible verified accounts; queue is limited to 10/hour/makerspace."
    operation["responses"][code] = json_response(output)
    if method == "post":
        operation["requestBody"] = {"required": True, "content": {"application/json": {"schema": ref("EventBroadcastInput")}}}
for action in ("queue", "cancel"):
    operation = deepcopy(base["post"])
    operation["operationId"] = f"api_v1_admin_events_broadcasts_{action}_create"
    operation["parameters"].append({"in": "path", "name": "campaign_id", "schema": integer, "required": True})
    operation["requestBody"] = {"content": {"application/json": {"schema": {"type": "object", "additionalProperties": False}}}}
    operation["responses"].pop("201", None)
    operation["responses"]["200"] = json_response("EventBroadcast")
    paths[route + "{campaign_id}/" + action + "/"] = {"post": operation}
operation = deepcopy(base["post"])
operation["operationId"] = "api_v1_admin_events_invites_bulk_create"
operation["description"] = "Requires manage_invitations and events.invites. Up to 200 email-bound invites; emails contain only event navigation, never admission codes. Verified account email is required for code-free admission."
operation["requestBody"] = {"required": True, "content": {"application/json": {"schema": ref("BulkInviteInput")}}}
operation["responses"]["201"] = json_response("BulkInviteResult")
paths["/api/v1/admin/events/{id}/invites/bulk/"] = {"post": operation}

for name, field in {"broadcasts_enabled": {"type": "boolean", "readOnly": True},
                    "report_features": {"type": "array", "items": text, "readOnly": True}}.items():
    components["EventAdmin"]["properties"][name] = field
    components["EventAdmin"]["required"] = sorted(set(components["EventAdmin"].get("required", [])) | {name})
subject_parameters = [{"in": "query", "name": "subject_kind", "schema": {"type": "string"},
                       "description": "Typed tenant-local subject; pair with subject_id. Refused on schedules and aggregates."},
                      {"in": "query", "name": "subject_id", "schema": {"type": "integer", "minimum": 1}}]
new_keys = {"event-registrations", "event-feedback", "event-attendance-pdf"}
for route, operations in paths.items():
    for method, operation in operations.items():
        if not isinstance(operation, dict) or "operationId" not in operation:
            continue
        if method == "post" and (route.endswith("/register/") and "/events/" in route or "/collaborative-events/" in route and route.endswith("/register/")):
            note = "Invite-only admission can resolve matching verified account email when invite_code is omitted; unverified code-free requests return email_verification_required. Normal eligibility, capacity and waiver rules still apply."
            if note not in operation.get("description", ""):
                operation["description"] = (operation.get("description", "") + " " + note).strip()
        is_report = "/analytics/" in route or "/reports/" in route and route.endswith("/export")
        if is_report:
            operation["parameters"] = [p for p in operation.get("parameters", []) if p.get("name") not in {"subject_kind", "subject_id"}] + deepcopy(subject_parameters)
            if "/makerspace/" in route:
                note = "Subject reports require event manage_registrations AND tenant VIEW_AUDIT; PDF requires full event management and an ended event."
                original = operation.get("description", "").replace(note, "").strip()
                operation["description"] = (original + " " + note).strip()
                for parameter in operation["parameters"]:
                    if parameter["name"] == "report_key" and "enum" in parameter["schema"]:
                        parameter["schema"]["enum"] = sorted(set(parameter["schema"]["enum"]) | new_keys)
            if "/reports/" in route and route.endswith("/export"):
                if "/makerspace/" in route:
                    next(p for p in operation["parameters"] if p["name"] == "format")["schema"]["enum"] = ["csv", "xlsx", "pdf"]
                operation["responses"]["200"]["content"]["application/pdf"] = {"schema": {"type": "string", "format": "binary"}}
                operation["responses"]["429"] = json_response("ReportError")
for name in ("ReportScheduleFilters",):
    components[name]["properties"].update({"subject_kind": {**text, "maxLength": 48}, "subject_id": {**integer, "minimum": 1}})
components["ReportKeyEnum"]["enum"] = sorted(set(components["ReportKeyEnum"]["enum"]) | new_keys)
components["EventRegistrationReportRow"] = obj({"registration_id": integer, "name": text,
    "email": text, "phone": text, "status": text, "created_at": date, "answers": text})
components["EventFeedbackReportRow"] = obj({"response_id": integer, "created_at": date,
    "registration_id": {**integer, "nullable": True}, "answers": text})
for kind in ("EventRegistration", "EventFeedback"):
    components[kind + "Report"] = obj({"rows": {"type": "array", "items": {"type": "array", "items": {}}},
        "typed_rows": {"type": "array", "items": ref(kind + "ReportRow")}})
    refs = components["AnalyticsReportResponse"]["oneOf"]
    if ref(kind + "Report") not in refs: refs.append(ref(kind + "Report"))
components["ReportExportFormatEnum"] = {"type": "string", "enum": ["csv", "xlsx", "pdf"]}
components["ReportCatalogItem"]["properties"]["allowed_formats"]["items"] = ref("ReportExportFormatEnum")
def extend_enums(value):
    if isinstance(value, dict):
        if value.get("enum") == ["csv", "xlsx"]:
            value["enum"] = ["csv", "xlsx", "pdf"]
        for item in value.values(): extend_enums(item)
    elif isinstance(value, list):
        for item in value: extend_enums(item)
# Only catalog allowed_formats expands; schedule format continues to be csv/xlsx.
extend_enums(components["ReportCatalogItem"]["properties"]["allowed_formats"])
path.write_text(json.dumps(schema, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
print("Lane D OpenAPI snapshot updated")

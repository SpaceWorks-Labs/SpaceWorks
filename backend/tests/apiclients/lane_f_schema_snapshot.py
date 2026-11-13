"""Host-independent snapshot update; run spectacular on the supported Django host too."""
import ast
from copy import deepcopy
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PATH = ROOT / "frontend/openapi-schema.json"
schema = json.loads(PATH.read_text(encoding="utf-8"))
components = schema["components"]["schemas"]
paths = schema["paths"]


def ref(name):
    return {"$ref": f"#/components/schemas/{name}"}


def obj(properties, required=None):
    return {"type": "object", "properties": deepcopy(properties),
            "required": sorted(properties) if required is None else required}


def response(name):
    return {"description": "", "content": {"application/json": {"schema": ref(name)}}}


def body(name):
    return {"required": True, "content": {"application/json": {"schema": ref(name)}}}


TEXT, INT, BOOL = {"type": "string"}, {"type": "integer"}, {"type": "boolean"}
DATE = {"type": "string", "format": "date-time"}
ERRORS = {str(code): {**response("HardwareRequestError"), "description": description}
          for code, description in (
    (400, "Invalid input or cursor."), (401, "Authentication or HMAC signature is invalid."),
    (403, "Authority denied, or recent_reauth_required for a protected mutation."),
    (404, "Unavailable or foreign target/module/feature."),
    (409, "State conflict, quota or last-governor/deletion protection."),
    (423, "Audited read refused while the source tenant is frozen."),
    (429, "Rate limit exceeded."), (503, "Required identity/delivery/source-gate dependency unavailable."))}


def op(method, route, output, *, input=None, status="200", tag="Reauthentication", security="jwtAuth", error_codes=(400, 401, 403, 429, 503)):
    item = {"operationId": route.strip("/").replace("/", "_").replace("{", "").replace("}", "") + "_" + method,
            "tags": [tag], "security": [{security: []}], "responses": {str(code): deepcopy(ERRORS[str(code)]) for code in error_codes}}
    item["responses"][status] = response(output) if output else {"description": "Deleted."}
    if input:
        item["requestBody"] = body(input)
    item["parameters"] = [{"in": "path", "name": name, "required": True, "schema": INT}
                          for name in ("id", "membership_id") if "{" + name + "}" in route]
    paths.setdefault(route, {})[method] = item
    return item


# Translate the simple concrete DRF reauthentication serializers from source so
# writeOnly/default/required/length constraints stay aligned without Django imports.
def field(call):
    name = call.func.attr
    args = {kw.arg: kw.value for kw in call.keywords}
    result = deepcopy({"BooleanField": BOOL, "IntegerField": INT,
                       "URLField": {**TEXT, "format": "uri"}}.get(name, TEXT))
    if name == "ListField":
        result = {"type": "array", "items": field(args["child"])}
    for key, target in (("write_only", "writeOnly"), ("read_only", "readOnly"),
                        ("max_length", "maxLength"), ("min_length", "minLength"), ("default", "default")):
        if key in args:
            result[target] = ast.literal_eval(args[key])
    return result


tree = ast.parse((ROOT / "backend/apps/accounts/serializers_reauthentication.py").read_text(encoding="utf-8"))
for cls in (node for node in tree.body if isinstance(node, ast.ClassDef)):
    properties, required = {}, []
    for node in cls.body:
        if not isinstance(node, ast.Assign) or not isinstance(node.value, ast.Call):
            continue
        name = node.targets[0].id
        properties[name] = field(node.value)
        args = {kw.arg: kw.value for kw in node.value.keywords}
        if not ("required" in args and ast.literal_eval(args["required"]) is False) and "default" not in args:
            required.append(name)
    components[cls.name.removesuffix("Serializer")] = obj(properties, required)

base = "/api/v1/auth/reauth"
op("get", base, "ReauthenticationStatus")
op("post", base, "ReauthenticationResult", input="Reauthentication")
for suffix, request, result in (
    ("/social/start", "ReauthenticationSocialStart", "ReauthenticationSocialStarted"),
    ("/social/complete", "ReauthenticationSocialComplete", "ReauthenticationResult"),
    ("/enrollment/email", "Empty", "ReauthenticationEmailSent"),
    ("/enrollment/confirm", "ReauthenticationEmailConfirm", "ReauthenticationEmailConfirmed")):
    op("post", base + suffix, result, input=request)
components["MFAEnrollmentStart"] = obj({"password": {**TEXT, "maxLength": 1024, "default": "", "writeOnly": True}}, [])
components["MFAStatus"]["properties"]["password_available"] = BOOL
for content in paths["/api/v1/auth/mfa"]["post"]["requestBody"]["content"].values():
    content["schema"] = ref("MFAEnrollmentStart")

components["OrganizationSelfCreate"] = obj({"name": {**TEXT, "maxLength": 200},
    "slug": {**TEXT, "maxLength": 50, "pattern": "^[-a-zA-Z0-9_]+$"},
    "description": TEXT, "website": {**TEXT, "format": "uri", "maxLength": 200}}, ["name", "slug"])
components["OrganizationCreationPolicy"] = obj({"enabled": BOOL, "eligible": BOOL,
    "max_owned": INT, "max_per_day": INT, "reason": TEXT})
route = "/api/v1/auth/organizations/self-service/"
op("get", route, "OrganizationCreationPolicy", tag="Auth", error_codes=(401, 403, 429))
op("post", route, "OrganizationDetail", input="OrganizationSelfCreate", status="201", tag="Auth", error_codes=(400, 401, 403, 409, 429))
components["OrganizationMembershipUpdate"] = obj({"status": {**TEXT, "enum": ["active", "suspended"]},
    "governance_actions": {"type": "array", "items": TEXT},
    "granted_actions": {"type": "array", "items": TEXT}}, [])
op("patch", "/api/v1/admin/organizations/{id}/memberships/{membership_id}/", "OrganizationMembership",
   input="OrganizationMembershipUpdate", tag="Admin organizations", error_codes=(400, 401, 403, 404, 409))
op("delete", "/api/v1/admin/organizations/{id}/", None, status="204", tag="Admin organizations", error_codes=(400, 401, 403, 404, 409))

components["IntegrationEvent"] = obj({"id": INT, "title": TEXT, "status": TEXT,
                                       "starts_at": DATE, "ends_at": DATE, "location": TEXT})
components["IntegrationParticipant"] = obj({"id": INT, "display_name": TEXT,
    "registered_at": DATE, "attended_at": {**DATE, "nullable": True}}, ["id", "display_name", "registered_at"])
for name in ("Event", "Participant"):
    components["Integration" + name + "Page"] = obj({"next_cursor": {**TEXT, "nullable": True},
        "results": {"type": "array", "items": ref("Integration" + name)}})
schema["components"].setdefault("securitySchemes", {})["ServerHMAC"] = {
    "type": "apiKey", "in": "header", "name": "X-Signature",
    "description": "Tenant-bound server HMAC; X-Client-Id and X-Timestamp required. Sign full path including query, timestamp, optional nonce and body."}
for route, result, paged in (("/api/v1/events/", "IntegrationEventPage", True),
    ("/api/v1/events/{id}/", "IntegrationEvent", False),
    ("/api/v1/events/{id}/participants/", "IntegrationParticipantPage", True)):
    item = op("get", route, result, tag="Server events", security="ServerHMAC", error_codes=(400, 401, 403, 404, 423, 429, 503))
    item["responses"].pop("409", None)
    item["summary"] = "Read tenant events or minimal participants using a signed server client"
    item["description"] = "events.api_read and events:read required. Participants additionally require participants:read; attendance dates additionally require participants:attendance:read. Explicit field allow-list; no contacts, answers, bearer credentials or payment data. Private/no-store."
    item["parameters"] += [{"in": "header", "name": name, "required": name != "X-Nonce", "schema": TEXT}
                            for name in ("X-Client-Id", "X-Timestamp", "X-Nonce")]
    if paged:
        item["parameters"] += [{"in": "query", "name": "cursor", "schema": {**TEXT, "maxLength": 2048}},
            {"in": "query", "name": "page_size", "schema": {**INT, "minimum": 1, "maximum": 200, "default": 100}}]
    paths[route]["head"] = deepcopy(item)
    paths[route]["head"]["operationId"] = item["operationId"] + "_head"
    paths[route]["head"]["responses"]["200"] = {"description": "Same authorization and headers as GET; empty body."}

# Explain step-up failures on existing sensitive mutations, too.
for route, operations in paths.items():
    sensitive = any(token in route for token in ("/api-clients", "/staff-grants", "/staff-invites", "/roles", "/staff-invitations"))
    for method, item in operations.items():
        if sensitive and method in {"post", "put", "patch", "delete"}:
            item.setdefault("responses", {})["403"] = deepcopy(ERRORS["403"])
            note = " Requires recent session-bound reauthentication (10 minutes); refresh does not renew it."
            if note.strip() not in item.get("description", ""):
                item["description"] = item.get("description", "") + note
PATH.write_text(json.dumps(schema, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
print("Lane F OpenAPI snapshot updated from reviewed serializers/routes")

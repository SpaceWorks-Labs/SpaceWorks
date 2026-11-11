"""Update the Lane E contract without Django; spectacular remains an integration gate."""
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


def obj(properties, required=None, strict=False):
    result = {"type": "object", "properties": deepcopy(properties)}
    if required:
        result["required"] = required
    if strict:
        result["additionalProperties"] = False
    return result


def json_response(name, description=""):
    return {"content": {"application/json": {"schema": ref(name)}}, "description": description}


integer = {"type": "integer"}
text = {"type": "string"}
number = {"type": "number", "format": "double"}
components["PositionedElement"] = obj({
    "field": {**text, "maxLength": 80},
    "x_mm": {**number, "minimum": 0}, "y_mm": {**number, "minimum": 0},
    "width_mm": {**number, "minimum": 0.5}, "height_mm": {**number, "minimum": 0.5},
    "font": {**text, "enum": ["sans", "serif"]},
    "font_size_pt": {**number, "minimum": 6, "maximum": 48},
    "bold": {"type": "boolean"}, "align": {**text, "enum": ["left", "center", "right"]},
    "colour": {**text, "pattern": "^#[0-9A-Fa-f]{6}$"},
}, ["field", "height_mm", "width_mm", "x_mm", "y_mm"], strict=True)
components["PositionedElement"]["description"] = "Reusable top-left millimetre box. Font is bundled; PDF rendering validates geometry and text overflow. Domain adapters validate field selectors."
badge = components["BadgeTemplate"]
badge["additionalProperties"] = False
badge["description"] = "Badge layout version 2. Legacy version 1 is converted on read. Only display fields and authorized custom-answer selectors are printable; email, phone and bearer QR credentials never print."
badge["properties"]["version"].update({"enum": [1, 2], "default": 2,
    "description": "Legacy version 1 input is accepted and converted; all reads return version 2."})
badge["properties"]["grid_mm"] = {**number, "minimum": 0.5, "maximum": 10, "default": 1}
badge["properties"]["elements"] = {"type": "array", "items": ref("PositionedElement"),
    "description": "Exactly one positioned box for each selected printable field."}
badge["properties"]["fields"]["description"] = "name, event_title, date_time, location, registration_number or custom:<question_id>. Email and phone selectors are refused. Custom-answer rendering requires the event's manage_registrations authority (tenant manage_events or an event staff grant)."
badge["properties"]["include_qr"].update({"default": False, "description": "Compatibility field, always normalized to false; bearer check-in credentials never print."})
components["CertificateParameters"] = obj({
    "version": {**integer, "minimum": 1, "maximum": 1},
    "page_width_mm": {**number, "minimum": 100, "maximum": 420},
    "page_height_mm": {**number, "minimum": 100, "maximum": 420},
    "name_box": ref("PositionedElement"),
    "grid_mm": {**number, "minimum": 0.5, "maximum": 10},
}, strict=True)
components["CertificateParameters"]["description"] = "Version 1 certificate layout. name_box.field must be name; only the recipient name is accepted. Defaults are A4 landscape with a bundled-font name box."
components["CertificateTemplateWrite"] = obj({
    "parameters": ref("CertificateParameters"),
    "artwork_id": {**integer, "minimum": 1, "nullable": True, "default": None},
}, ["parameters"], strict=True)
components["CertificateTemplateRevision"] = obj({
    "id": {**integer, "nullable": True}, "parameters": ref("CertificateParameters"),
    "artwork_id": {**integer, "nullable": True},
    "created_at": {**text, "format": "date-time", "nullable": True},
}, ["artwork_id", "created_at", "id", "parameters"])
components["CertificateArtworkPresign"] = obj({
    "content_type": {**text, "enum": ["image/png", "image/jpeg"]},
    "content_length": {**integer, "minimum": 1, "maximum": 10485760},
}, ["content_length", "content_type"], strict=True)
components["CertificateArtworkUpload"] = obj({
    "id": integer, "upload_url": {**text, "format": "uri"},
    "headers": {"type": "object", "additionalProperties": text},
}, ["headers", "id", "upload_url"])
components["CertificateArtwork"] = obj({"id": integer}, ["id"])
components.setdefault("Strict", obj({}, strict=True))
components["EventAdmin"]["properties"]["badge_sensitive_fields_allowed"] = {"type": "boolean", "readOnly": True,
    "description": "Live event manage_registrations authority (tenant manage_events or an event staff grant); permits custom-answer badge printing."}
components["EventAdmin"]["required"] = sorted(set(components["EventAdmin"].get("required", [])) | {"badge_sensitive_fields_allowed"})
components["EventAdmin"]["properties"]["ticketing_features"] = {
    "type": "array", "items": text, "readOnly": True,
    "description": "Enabled event feature keys, including events.certificate_designer when configured.",
}
error_descriptions = {400: "Invalid layout, field selector, upload or text overflow.", 401: "Authentication required.",
    403: "Live event edit_details authority and events.certificate_designer are required.",
    404: "Event or owned private artwork not found.", 409: "Event, quota or immutable artwork state conflict.",
    429: "Credential render or artwork upload rate limit exceeded.", 503: "Private storage or rendering unavailable."}
errors = {str(code): json_response("HardwareRequestError", description) for code, description in error_descriptions.items()}
base = paths["/api/v1/admin/events/{id}/badge-template/"]["get"]


def operation(operation_id, response_schema, description, *, request=None, code="200", media="application/json", artwork=False):
    result = {"operationId": operation_id, "parameters": deepcopy(base["parameters"]),
              "tags": ["Admin events"], "security": deepcopy(base["security"]),
              "description": "Requires authenticated active staff, live event edit_details and events.certificate_designer. " + description + " Responses are private/no-store.",
              "responses": deepcopy(errors)}
    if artwork:
        result["parameters"].append({"in": "path", "name": "artwork_id", "schema": integer, "required": True})
    result["responses"][code] = {"content": {media: {"schema": response_schema}}, "description": ""}
    if request:
        result["requestBody"] = {"required": request != "Strict", "content": {
            content_type: {"schema": ref(request)} for content_type in ("application/json", "application/x-www-form-urlencoded", "multipart/form-data")}}
    return result


prefix = "/api/v1/admin/events/{id}/"
paths[prefix + "certificate-template/"] = {
    "get": operation("api_v1_admin_events_certificate_template_retrieve", ref("CertificateTemplateRevision"),
        "Returns the current immutable revision, or default layout with null ID and created_at."),
    "post": operation("api_v1_admin_events_certificate_template_create", ref("CertificateTemplateRevision"),
        "Every save creates a new immutable revision. Artwork must be promoted and owned by this event. Existing pending, failed and retried issuances retain their frozen layout/artwork.", request="CertificateTemplateWrite", code="201"),
}
paths[prefix + "certificate-template/preview.pdf"] = {"post": operation(
    "api_v1_admin_events_certificate_template_preview.pdf_create", {"type": "string", "format": "binary"},
    "Throttled PDF preview uses a fixed sample recipient and issuance geometry/artwork/overflow rules. Recipient data is never accepted.",
    request="CertificateTemplateWrite", media="application/pdf")}
paths[prefix + "certificate-artwork/"] = {"post": operation(
    "api_v1_admin_events_certificate_artwork_create", ref("CertificateArtworkUpload"),
    "Reserve owned private artwork and obtain a ten-minute staging-only PUT with exact MIME headers. PNG/JPEG up to 10 MiB. Final object keys are server-owned.", request="CertificateArtworkPresign", code="201")}
paths[prefix + "certificate-artwork/{artwork_id}/finalize/"] = {"post": operation(
    "api_v1_admin_events_certificate_artwork_finalize_create", ref("CertificateArtwork"),
    "Validate bounded decoded pixels, strip metadata and promote once. Quota/ownership/authority are rechecked; retries are idempotent.", request="Strict", artwork=True)}
paths[prefix + "certificate-artwork/{artwork_id}/"] = {"get": operation(
    "api_v1_admin_events_certificate_artwork_retrieve", {"type": "string", "format": "binary"},
    "Throttled authenticated private artwork read. No public route or object URL is exposed.", media="image/png", artwork=True)}
for method in ("get", "put"):
    paths[prefix + "badge-template/"][method]["description"] = "Requires live event edit_details authority. Version 1 templates convert on read to positioned version 2 layouts. Contacts and bearer QR credentials never print."
badge_pdf = paths[prefix + "badges.pdf"]["post"]
badge_pdf["description"] = "Throttled, audited private badge PDF. Requires check_in; scoped check-in actors may print only attended registrations and cannot override templates. Custom answers additionally require event manage_registrations (tenant manage_events or an event staff grant); tenant VIEW_AUDIT is not required. No contact details or bearer QR credentials print."
badge_pdf["responses"]["429"] = json_response("HardwareRequestError", "Credential render rate limit exceeded.")
for route in ("/api/v1/admin/event-certificates/{id}/download/", "/api/v1/member/makerspaces/{makerspace_id}/event-certificates/{id}/download/"):
    download = paths[route]["get"]
    download["description"] = "Throttled, audited certificate download. Existing staff-management or exact participant-ownership checks remain required. The immutable issuance snapshot controls layout and artwork."
    download["responses"]["429"] = json_response("HardwareRequestError", "Credential render rate limit exceeded.")
path.write_text(json.dumps(schema, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
print("Lane E OpenAPI snapshot updated: five certificate routes and shared print schema")

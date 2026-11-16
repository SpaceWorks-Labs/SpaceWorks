"""Reviewed OpenAPI delta for the Django-free host. Verify with live spectacular later."""

from copy import deepcopy
import json
from pathlib import Path

PATH = Path(__file__).resolve().parents[3] / "frontend/openapi-schema.json"
schema = json.loads(PATH.read_text(encoding="utf-8"))
components, paths = schema["components"]["schemas"], schema["paths"]


def ref(name):
    return {"$ref": "#/components/schemas/" + name}


def obj(properties, required=(), **extra):
    return {"type": "object", "properties": properties, "required": list(required), **extra}


def string(maximum=None, **values):
    return {"type": "string", **({"maxLength": maximum} if maximum else {}), **values}


section = {
    "kind": string(enum=["rules", "amenity", "faq", "link", "sponsor", "gallery"]),
    "slug": string(80, pattern="^[-a-zA-Z0-9_]+$"), "title": string(200),
    "body": string(10000, default=""), "url": string(500, format="uri", default=""),
    "asset_id": {"type": "integer", "minimum": 1, "nullable": True, "default": None},
    "visibility": string(enum=["draft", "published"], default="draft"),
    "position": {"type": "integer", "minimum": 0, "maximum": 1000, "default": 0},
}
components["BookingWebsiteSectionInput"] = obj(section, ("kind", "slug", "title"), additionalProperties=False)
components["BookingWebsiteSection"] = obj({**section,
    "image_url": string(nullable=True), "image_alt_text": string(),
}, (*section.keys(), "image_url", "image_alt_text"))
components["BookingWebsiteContentInput"] = obj({
    "revision": {"type": "integer", "minimum": 0},
    "sections": {"type": "array", "maxItems": 100, "items": ref("BookingWebsiteSectionInput")},
}, ("revision", "sections"), additionalProperties=False)
components["BookingWebsiteReleaseInput"] = obj({
    "revision": {"type": "integer", "minimum": 1}, "released": {"type": "boolean"},
}, ("revision", "released"), additionalProperties=False)
components["BookingWebsiteAssetInput"] = obj({
    "file": string(format="binary"), "alt_text": string(200),
    "replace_id": {"type": "integer", "minimum": 1},
}, ("file", "alt_text"), additionalProperties=False)
components["BookingWebsiteAsset"] = obj({
    "id": {"type": "integer"}, "alt_text": string(), "size_bytes": {"type": "integer"},
}, ("id", "alt_text", "size_bytes"))
components["BookingWebsite"] = obj({
    "public_url": string(format="uri", readOnly=True), "embed_path": string(readOnly=True),
    "revision": {"type": "integer"}, "released": {"type": "boolean"},
    "sections": {"type": "array", "items": ref("BookingWebsiteSection")},
    "assets": {"type": "array", "items": ref("BookingWebsiteAsset")},
}, ("revision", "released", "sections"))
components["BookingPublicRules"] = obj({key: {"type": "integer"} for key in (
    "minimum_minutes", "maximum_minutes", "lead_minutes", "advance_days", "cancellation_cutoff_hours",
)}, ("minimum_minutes", "maximum_minutes", "lead_minutes", "advance_days", "cancellation_cutoff_hours"))
detail = deepcopy(components["PublicBookableSpace"])
detail["properties"].update(payment_amount={"type": "string", "format": "decimal"},
    currency=string(), rules=ref("BookingPublicRules"),
    website={"allOf": [ref("BookingWebsite")], "nullable": True})
detail["required"] = sorted(set(detail.get("required", [])) | {"payment_amount", "currency", "rules", "website"})
components["PublicBookingResource"] = detail
for field in ("website_enabled", "embed_enabled"):
    components["BookableSpaceAdmin"]["properties"][field] = {"type": "boolean", "readOnly": True}
    components["BookableSpaceAdmin"]["required"] = sorted(set(components["BookableSpaceAdmin"]["required"]) | {field})

staff_base = paths["/api/v1/admin/spaces/{id}/pass-template/"]["get"]
public_base = paths["/api/v1/public/{makerspace_slug}/spaces/{public_token}/availability/"]["get"]


def operation(base, identity, response, description, *, body=None, upload=False, image=False, code="200", asset=False):
    result = deepcopy(base)
    result.update(operationId=identity, description=description, tags=["Booking website"] if base is staff_base else ["Public booking website"])
    result["parameters"] = [p for p in result.get("parameters", []) if p.get("in") == "path"]
    if asset:
        result["parameters"].append({"in": "path", "name": "asset_id", "required": True, "schema": {"type": "integer"}})
    result.pop("requestBody", None)
    result["responses"] = {str(status): {"description": text, "content": {"application/json": {"schema": ref("Error")}}}
        for status, text in ((400, "Invalid content, unknown fields, disabled feature or stale revision."),
            (404, "Unknown, private, inactive, foreign or unreleased content."), (429, "Rate limit exceeded."),
            (503, "Image storage or tenant write gate unavailable."))}
    if base is staff_base:
        result["responses"].update({str(status): {"description": text, "content": {"application/json": {"schema": ref("Error")}}}
            for status, text in ((401, "Staff sign in required."), (403, "Missing live resource permission or wrong origin."), (423, "Tenant frozen."))})
    else:
        result.pop("security", None)
    result["responses"][code] = {"description": "No-store; public images also enforce live release and ownership."}
    if code != "204":
        result["responses"][code]["content"] = {"image/webp" if image else "application/json": {
            "schema": string(format="binary") if image else ref(response)}}
    if body:
        result["requestBody"] = {"required": True, "content": {"multipart/form-data" if upload else "application/json": {"schema": ref(body)}}}
    return result


base = "/api/v1/admin/spaces/{id}/website/"
paths[base] = {
    "get": operation(staff_base, "admin_spaces_website_retrieve", "BookingWebsite", "Private preview requires edit_details or publish_page; bookings.website required."),
    "put": operation(staff_base, "admin_spaces_website_update", "BookingWebsite", "Requires live edit_details under resource/tenant locks; revision match; audits revision only.", body="BookingWebsiteContentInput"),
}
paths[base + "release/"] = {"post": operation(staff_base, "admin_spaces_website_release_create", "BookingWebsite", "Requires publish_page and current page revision. Release cannot activate a private/inactive resource.", body="BookingWebsiteReleaseInput")}
paths[base + "assets/"] = {"post": operation(staff_base, "admin_spaces_website_assets_create", "BookingWebsiteAsset", "edit_details; private multipart upload, 5 MB, single-frame 16 megapixels, sniffed/re-encoded WebP. Replacement must belong to this page.", body="BookingWebsiteAssetInput", upload=True, code="201")}
paths[base + "assets/{asset_id}/"] = {
    "get": operation(staff_base, "admin_spaces_website_assets_retrieve", None, "Separate edit_details-authorized private preview.", image=True, asset=True),
    "delete": operation(staff_base, "admin_spaces_website_assets_destroy", None, "edit_details; audit and post-commit object cleanup/quota release.", code="204", asset=True),
}
base = "/api/v1/public/{makerspace_slug}/spaces/{public_token}/"
paths[base] = {"get": operation(public_base, "public_spaces_retrieve", "PublicBookingResource", "Active public resource core with flat price and approved rule summaries. Website null unless feature enabled and released; no reservation identities or internal buffers.")}
paths[base + "website/"] = {"get": operation(public_base, "public_spaces_website_retrieve", "BookingWebsite", "Only live released page with published sections. Unreleased/private/disabled are uniform 404s.")}
paths[base + "website/assets/{asset_id}/"] = {"get": operation(public_base, "public_spaces_website_assets_retrieve", None, "Private image bytes require current public resource, feature, release and a published same-page reference. No object URLs.", image=True, asset=True)}
paths["/api/v1/discover/{kind}/"]["get"]["description"] = "Deployment-local, directory-consented subjects, paginated 24. Events accept q/date_from/date_to; bookings accept q/kind/location/page and reject date filters. Does not widen direct visibility."
parameters = paths["/api/v1/discover/{kind}/"]["get"].setdefault("parameters", [])
for name, description in (("kind", "Booking resource kind (query filter); events use date filters instead."),
                          ("location", "Booking resource location contains this text.")):
    parameters[:] = [p for p in parameters if (p.get("in"), p.get("name")) != ("query", name)]
    parameters.append({"in": "query", "name": name, "schema": {"type": "string"}, "description": description})
PATH.write_text(json.dumps(schema, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
print("BK-F: seven routes / nine operations, private/public allow-list schemas and resource feature flags.")

"""Editorial content plus per-read live privacy; cached bodies never authorize."""

from copy import deepcopy
from .models_profiles import PublicHandle
from .platform import module_enabled, feature_enabled
from .public_page_access import canonical_url
from .public_page_contract import PALETTES
from .public_page_markdown import document_description, excerpt
from .public_profile_access import profile_is_public, _request_tenant_ids


def functional_links(space):
    from .public_page_access import canonical_origin
    from .editions import public_surface_available
    origin = canonical_origin(space)
    home = "" if space.frontend_domain and space.frontend_domain_status == "verified" else f"/m/{space.slug}"
    available = {key: module_enabled(space, key) and public_surface_available(key)
                 for key in ("events", "bookings", "machines", "membership")}
    available["inventory"] = bool(module_enabled(space, "public_inventory") and public_surface_available("public_inventory") and space.public_inventory_enabled
                                  and feature_enabled(space, "loans.enabled"))
    routes = {"inventory": "", "events": "/events", "bookings": "/bookings",
              "machines": "/machines", "membership": "/member"}
    return {"links": [{"family": key, "url": f"{origin}{home}{path}"}
                      for key, path in routes.items() if available[key]]}


def project_team(entries, revision, request):
    from .profile_services import display_name_for
    from apps.inventory.public_image_storage import public_url
    references = {str(row.slot): row.profile for row in revision.member_references.select_related(
        "profile__membership__makerspace", "profile__membership__user")}
    # One handle query for the whole section instead of one per member row.
    claims = {(row.profile_id, row.user_id): row for row in PublicHandle.objects.filter(
        profile__in=[profile for profile in references.values() if profile is not None])}
    result = []
    scopes = _request_tenant_ids(request) if request else []
    for row in entries:
        if row["kind"] == "explicit":
            result.append(row)
            continue
        profile = references.get(row.get("member_slot_id", row["id"]))
        if not profile_is_public(profile) or any(pk != profile.membership.makerspace_id for pk in scopes):
            continue
        claim = claims.get((profile.pk, profile.membership.user_id))
        if claim is None:
            continue
        from .public_profile_share import profile_url
        result.append({"id": row["id"], "kind": "member", "role": row["role"],
                       "display_name": display_name_for(profile.membership), "handle": claim.handle,
                       "url": profile_url(claim), "avatar_url": public_url(profile.avatar_key) or None})
    return result


def project_sections(kind, owner, revision, *, request=None, image_url=None, document=None):
    from .public_page_derived import derived_payload
    document = document if document is not None else revision.document
    result = []
    for original in document["sections"]:
        if not original["enabled"]:
            continue
        section = deepcopy(original)
        payload, key = section["payload"], section["type"]
        if key == "team":
            payload["entries"] = project_team(payload["entries"], revision, request)
        elif key == "gallery":
            assets = {row.pk: row for row in revision.page.assets.all()}
            payload["items"] = [{"url": image_url(row["asset_id"]) if image_url else None, "alt": assets[row["asset_id"]].alt_text,
                                 "caption": row["caption"]} for row in payload["items"] if row["asset_id"] in assets]
        elif key in ("functional_content", "linked_makerspaces", "organization_events", "upcoming_events", "stats", "location"):
            payload = derived_payload(kind, owner, key, payload, request=request)
            if payload is None:
                continue
        section["payload"] = payload
        result.append(section)
    return result


def presentation(kind, owner, document, *, legacy_accent=""):
    from .theme_contrast import derive_palette, rgb
    theme = deepcopy(owner.theme_config) if kind == "makerspace" else {}
    if legacy_accent and rgb(legacy_accent):
        theme["primary_color"] = legacy_accent
    choice = document.get("accent_choice") or "inherit"
    if choice in PALETTES:
        theme["primary_color"] = PALETTES[choice]
    return {"accent_choice": choice, "resolved_theme": {
        "theme_config": theme, "light": derive_palette(theme, "light"), "dark": derive_palette(theme, "dark")}}


def page_description(kind, owner, document):
    # Makerspaces have no description field; organizations fall back to About too.
    own = excerpt(owner.description) if kind == "organization" else ""
    return own or document_description(document)


def projection(kind, owner, page, *, request=None):
    from apps.inventory.public_image_storage import public_url
    revision, claim = page.published_revision, PublicHandle.objects.filter(**{kind: owner}).first()
    document = revision.document
    base = (f"/api/v1/public/{owner.slug}/page/" if kind == "makerspace"
            else f"/api/v1/public/organizations/{owner.slug}/page/")
    image = lambda pk: f"{base}assets/{pk}/"
    title = (owner.branding_config.get("display_name") or owner.name) if kind == "makerspace" else owner.name
    cover = None
    if document["cover_mode"] == "asset":
        asset = page.assets.get(pk=document["cover_asset_id"])
        cover = {"url": image(asset.pk), "alt": asset.alt_text}
    elif document["cover_mode"] == "inherit":
        key = (owner.cover_image_key or owner.logo_key) if kind == "makerspace" else owner.logo_key
        if key:
            cover = {"url": public_url(key), "alt": owner.name}
    return {"schema_version": 1, "kind": kind, "canonical_url": canonical_url(kind, owner, claim.handle if claim else None),
            "title": title, "description": page_description(kind, owner, document), "publication_token": str(revision.pk),
            "cover": cover, "presentation": presentation(kind, owner, document),
            "sections": project_sections(kind, owner, revision, request=request, image_url=image)}

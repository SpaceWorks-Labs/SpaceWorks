"""Project selected immutable publication; never fill it from working children."""

from copy import deepcopy
from datetime import datetime, timedelta
from .website_content import SECTION_GROUPS, page_defaults


def enabled(document, group):
    return document.get("section_enabled", {}).get(group, True) is True


def snapshot_sessions(revision, *, public):
    document = revision.document
    if public and not enabled(document, "SCHEDULE"):
        return []
    return [row for row in document["sessions"] if not public or row["visibility"] == "published"]


def project_revision(target, page, *, image_url=None, request=None):
    from .models import EventSeries
    revision = page.published_revision
    document = deepcopy(revision.document)
    allowed = {row["slug"]: row for row in document["sections"] if row["visibility"] == "published"
               and enabled(document, SECTION_GROUPS.get(row["kind"]))}
    assets = {row.pk: row for row in page.assets.filter(pk__in=[row.get("asset_id") for row in allowed.values()])}
    for row in allowed.values():
        pk = row.get("asset_id")
        row["image_url"] = image_url(pk) if pk and image_url else None
        row["image_alt_text"] = assets[pk].alt_text if pk in assets else ""
    inherited = bool(page.series_id and not isinstance(target, EventSeries))
    delta = target.starts_at - revision.source_anchor_start if inherited else timedelta()
    rows, delays = [], {}
    for original in sorted(snapshot_sessions(revision, public=True), key=lambda row: (row["starts_at"], row["slug"])):
        row = deepcopy(original)
        delay = max(delays.get(row["track"], 0), row["delay_minutes"])
        delays[row["track"]] = delay
        lo, hi = datetime.fromisoformat(row["starts_at"]), datetime.fromisoformat(row["ends_at"])
        row.update(starts_at=lo + delta, ends_at=hi + delta,
                   effective_starts_at=lo + delta + timedelta(minutes=delay),
                   effective_ends_at=hi + delta + timedelta(minutes=delay),
                   track=row["track"] if row["track"] in allowed else None,
                   room=row["room"] if row["room"] in allowed else None,
                   speakers=[slug for slug in row["speakers"] if slug in allowed])
        rows.append(row)
    result = {key: document.get(key, value) for key, value in page_defaults().items()}
    result.update(revision=page.revision, released=True, inherited=inherited, sections=list(allowed.values()), sessions=rows)
    from apps.makerspaces.public_page_projection import project_sections, presentation
    editorial = document.get("editorial_document", {})
    if editorial:
        result["editorial_document"] = {**editorial, "sections": project_sections(
            "event", target, revision, request=request, image_url=image_url, document=editorial)}
        result["presentation"] = presentation("makerspace", target.makerspace, editorial,
                                               legacy_accent=document.get("accent_color", ""))
    result["cover"] = None
    if enabled(document, "HERO"):
        if editorial.get("cover_mode") == "asset":
            asset = page.assets.get(pk=editorial["cover_asset_id"])
            result["cover"] = {"url": image_url(asset.pk) if image_url else None, "alt": asset.alt_text}
        elif editorial.get("cover_mode", "inherit") == "inherit":
            from apps.inventory.public_image_storage import public_url
            key = target.image_key
            if target.series_id and "image_key" not in (target.series_override_fields or []):
                key = target.series.image_key
            key = key or target.makerspace.cover_image_key or target.makerspace.logo_key
            if key:
                result["cover"] = {"url": public_url(key), "alt": target.title}
    if not enabled(document, "VENUE"):
        result["venue"] = None
    if not enabled(document, "HERO"):
        result["tagline"] = ""
        if result.get("editorial_document"):
            result["editorial_document"]["cover_asset_id"] = None
            result["editorial_document"]["cover_mode"] = "none"
    if not enabled(document, "EDITORIAL"):
        result["editorial_document"] = None
    return result


def visible_asset_ids(revision):
    document = revision.document
    ids = {row["asset_id"] for row in document["sections"] if row.get("asset_id") is not None
           and row["visibility"] == "published" and enabled(document, SECTION_GROUPS.get(row["kind"]))}
    editorial = document.get("editorial_document", {})
    if enabled(document, "HERO") and editorial.get("cover_mode") == "asset":
        ids.add(editorial["cover_asset_id"])
    if enabled(document, "EDITORIAL"):
        for section in editorial.get("sections", []):
            if section["enabled"] and section["type"] == "gallery":
                ids.update(row["asset_id"] for row in section["payload"]["items"])
    return ids

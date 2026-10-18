"""Allow-list projection and track delay calculation, shared by all event paths."""

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from .models import EventSeries
from .models_website import EventPage
from .website_content import PAGE_FIELDS, SECTION_FIELDS, SECTION_GROUPS, group_enabled, page_defaults
from .website_visibility import effective_page, visible_page


def window(target):
    if isinstance(target, EventSeries):
        start = datetime.combine(target.dtstart_local_date, target.dtstart_local_time,
                                 tzinfo=ZoneInfo(target.recurrence_timezone))
        start = start.astimezone(timezone.utc)
        return start, start + timedelta(minutes=target.duration_minutes)
    return target.starts_at.astimezone(timezone.utc), target.ends_at.astimezone(timezone.utc)


def project(target, *, public=False, image_url=None, request_context=None):
    if public:
        page = visible_page(target)
    elif isinstance(target, EventSeries):
        page = EventPage.objects.filter(series=target).first()
    else:
        page = effective_page(target)
    return project_page(target, page, public=public, image_url=image_url, request_context=request_context)


def project_page(target, page, *, public=False, image_url=None, request_context=None):
    empty = {**page_defaults(), "revision": 0, "released": False, "inherited": False, "sections": [], "sessions": [], "assets": []}
    if page is None:
        return empty
    sections = list(page.sections.select_related("asset"))
    allowed = {row.pk: row for row in sections if not public or (
        row.visibility == "published" and group_enabled(page, SECTION_GROUPS.get(row.kind)))}
    delta = timedelta()
    inherited = bool(page.series_id and not isinstance(target, EventSeries))
    if inherited:
        delta = target.starts_at - window(page.series)[0]
    section_rows = []
    for row in allowed.values():
        asset_url = image_url(row.asset_id) if row.asset_id and image_url else None
        section_rows.append({**{key: getattr(row, key) for key in SECTION_FIELDS}, "asset_id": row.asset_id,
                             "image_url": asset_url, "image_alt_text": row.asset.alt_text if row.asset_id else ""})
    session_rows, delays = [], {}
    sessions = page.sessions.select_related("track", "room").prefetch_related("speaker_links__speaker").order_by("starts_at", "slug")
    for row in sessions if not public or group_enabled(page, "SCHEDULE") else []:
        # A hidden session never shifts the released schedule or reveals hidden track data.
        if public and row.visibility != "published":
            continue
        delay = max(delays.get(row.track_id, 0), row.delay_minutes)
        # Draft delays affect only their own preview, never the published programme.
        if row.visibility == "published":
            delays[row.track_id] = delay
        shift = delta + timedelta(minutes=delay)
        session_rows.append({
            "slug": row.slug, "title": row.title, "body": row.body,
            "starts_at": row.starts_at + delta, "ends_at": row.ends_at + delta,
            "effective_starts_at": row.starts_at + shift, "effective_ends_at": row.ends_at + shift,
            "delay_minutes": row.delay_minutes, "visibility": row.visibility,
            "track": row.track.slug if row.track_id in allowed else None,
            "room": row.room.slug if row.room_id in allowed else None,
            "speakers": [speaker.slug for speaker in [link.speaker for link in row.speaker_links.all()] if speaker.pk in allowed],
        })
    result = {**{key: getattr(page, key) for key in PAGE_FIELDS},
              "revision": page.revision, "released": page.released, "inherited": inherited,
              "sections": section_rows, "sessions": session_rows}
    if public and not group_enabled(page, "VENUE"):
        result["venue"] = None
    if public and not group_enabled(page, "HERO"):
        result["tagline"] = ""
    if public and not isinstance(target, EventSeries):
        from .contracts.pages_registration import project_sections
        result["programme_sections"] = project_sections(event_id=target.pk, request_context=request_context)
    if not public:
        result["assets"] = list(page.assets.values("id", "alt_text", "size_bytes"))
    return result

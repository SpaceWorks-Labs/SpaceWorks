"""Independently compare restored relational working rows with the draft snapshot.

Only retained models and the model-free field vocabulary are used; no public or
editor runtime service needs to exist when Events is tombstoned.
"""

from copy import deepcopy
from datetime import UTC, datetime, timedelta
import json
from zoneinfo import ZoneInfo

from .public_page_verification import refuse


def owner_window(target):
    from apps.events.models import EventSeries
    if isinstance(target, EventSeries):
        lo = datetime.combine(target.dtstart_local_date, target.dtstart_local_time,
                              tzinfo=ZoneInfo(target.recurrence_timezone)).astimezone(UTC)
        return lo, lo + timedelta(minutes=target.duration_minutes)
    return target.starts_at.astimezone(UTC), target.ends_at.astimezone(UTC)


def verify_released_window(target, revision, *, inherited=False):
    if revision.document["section_enabled"].get("SCHEDULE", True) is not True:
        return
    start, end = owner_window(target)
    for session in revision.document["sessions"]:
        if session["visibility"] != "published":
            continue
        lo, hi = datetime.fromisoformat(session["starts_at"]), datetime.fromisoformat(session["ends_at"])
        if inherited:
            lo, hi = start + (lo - revision.source_anchor_start), start + (hi - revision.source_anchor_start)
        if not start <= lo < hi <= end:
            refuse("released session outside effective owner window")


def verify_working_draft(page):
    from apps.events.website_content import PAGE_FIELDS, SECTION_FIELDS
    from apps.makerspaces.public_page_markdown import rendering_policy
    if not page.draft_revision_id:
        if page.sections.filter(is_working=True).exists() or page.sessions.exists():
            refuse("nonempty working website without a draft")
        return
    revision = page.draft_revision
    actual = {field: deepcopy(getattr(page, field)) for field in PAGE_FIELDS}
    actual["sections"] = [
        {**{field: getattr(row, field) for field in SECTION_FIELDS},
         "asset_id": row.asset_id, "body_rendering": rendering_policy(row.body)}
        for row in page.sections.filter(is_working=True)
    ]
    actual["sessions"] = [
        {"session_id": str(row.identity_id), "slug": row.slug, "title": row.title, "body": row.body,
         "body_rendering": rendering_policy(row.body), "starts_at": row.starts_at, "ends_at": row.ends_at,
         "delay_minutes": row.delay_minutes, "visibility": row.visibility,
         "track": row.track.slug if row.track_id else None, "room": row.room.slug if row.room_id else None,
         "speakers": [link.speaker.slug for link in row.speaker_links.select_related("speaker").order_by("pk")]}
        for row in page.sessions.select_related("track", "room").order_by("starts_at", "slug")
    ]
    expected = deepcopy(revision.document)
    profiles = {str(row.slot): row.profile_id for row in revision.member_references.all()}
    for section in actual["editorial_document"]["sections"]:
        if section["type"] == "team":
            entries = []
            for row in section["payload"]["entries"]:
                if row["kind"] == "member":
                    if profiles.get(row["id"]) is None:
                        continue
                    if profiles.get(row["id"]) != row.pop("profile_id"):
                        refuse("working member link differs from draft")
                    row["member_slot_id"] = row["id"]
                entries.append(row)
            section["payload"]["entries"] = entries
    for section in expected["editorial_document"]["sections"]:
        if section["type"] == "team":
            section["payload"]["entries"] = [row for row in section["payload"]["entries"]
                if row["kind"] != "member" or profiles.get(row["member_slot_id"]) is not None]
    # Drafts saved before speaker order was pinned may hold heap order; speaker
    # membership, not its order, is what a restore must preserve.
    for document in (actual, expected):
        for session in document["sessions"]:
            session["speakers"] = sorted(session["speakers"])
    def encode(value):
        return json.dumps(value, sort_keys=True, default=lambda row: row.isoformat() if isinstance(row, datetime) else str(row))
    if encode(actual) != encode(expected) or revision.source_anchor_start != owner_window(page.event or page.series)[0]:
        refuse("working website differs from selected draft")

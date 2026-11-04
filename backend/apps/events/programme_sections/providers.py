"""Hackathon sections extend pages; they never reopen an expired/retracted website."""

from dataclasses import dataclass
from typing import Protocol

from django.http import Http404

from apps.events.judging.models_definitions import HackathonPrize
from apps.events.judging.ports import runtime
from apps.events.submissions.gallery_models import GalleryEntry
from apps.events.submissions.gallery_projection import project_entry, public_event, public_results

KINDS = ("prizes", "judges", "mentors", "project_gallery", "results")


@dataclass(frozen=True, kw_only=True)
class Section:
    id: int
    event_id: int
    kind: str
    options: dict


class PagesAdapter(Protocol):
    def require_released_section(self, *, event_id: int, section_id: int, request_context) -> Section:
        """Pages gate: current event window, effective-page release, group and section visibility."""
        ...

    def role_cards(self, *, event_id: int, role: str) -> tuple[dict, ...]:
        """C approved display-on-page roles composed with E live public-profile/photo consent."""
        ...


_pages: PagesAdapter | None = None


def validate_options(value):
    if not isinstance(value, dict) or set(value) - {"ids", "layout", "limit"}:
        raise ValueError("Use stable IDs and supported presentation options only.")
    ids = value.get("ids", [])
    if (not isinstance(ids, list) or len(ids) > 100 or any(type(pk) is not int or pk <= 0 for pk in ids)
            or len(set(ids)) != len(ids)):
        raise ValueError("Use at most 100 distinct positive IDs.")
    if value.get("layout", "grid") not in ("grid", "list"):
        raise ValueError("Unknown section layout.")
    limit = value.get("limit", 12)
    if type(limit) is not int or not 1 <= limit <= 100:
        raise ValueError("Use a section limit from 1 to 100.")
    return {"ids": ids, "layout": value.get("layout", "grid"), "limit": limit}


def install(adapter: PagesAdapter, register):
    """G/pages calls this explicitly; importing the package registers nothing."""
    global _pages
    _pages = adapter
    for kind in KINDS:
        register(kind=kind, validator=validate_options, provider=project_public)


def project_public(*, event_id, section_id, request_context):
    if _pages is None:
        raise Http404
    section = _pages.require_released_section(event_id=event_id, section_id=section_id, request_context=request_context)
    if section.event_id != event_id or section.id != section_id or section.kind not in KINDS:
        raise Http404
    event = public_event(event_id=event_id, request_context=request_context, gallery=section.kind == "project_gallery")
    options = validate_options(section.options)
    if section.kind == "prizes":
        rows = HackathonPrize.objects.filter(event_id=event_id).order_by("order", "pk")
        if options["ids"]:
            rows = rows.filter(pk__in=options["ids"])
        values = [{"id": p.pk, "name": p.name, "description": p.description,
                   "award_count": p.award_count} for p in rows[:options["limit"]]]
    elif section.kind in ("judges", "mentors"):
        # The E/C adapter returns only live-public cards; project explicit keys again.
        values = [{key: card[key] for key in ("display_name", "profile_url", "photo_url") if key in card}
                  for card in _pages.role_cards(event_id=event_id, role="judge" if section.kind == "judges" else "mentor")]
    elif section.kind == "results":
        values = public_results(event)["awards"]
    else:
        values = []
        rows = GalleryEntry.objects.filter(event_id=event_id, hidden_at__isnull=True).select_related("event").order_by("pk")
        if options["ids"]:
            rows = rows.filter(pk__in=options["ids"])
        for row in rows:
            try:
                values.append(project_entry(row))
            except Http404:
                continue
            if len(values) >= options["limit"]:
                break
    return {"kind": section.kind, "layout": options["layout"], "items": values[:options["limit"]]}

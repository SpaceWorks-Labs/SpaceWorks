"""Versioned native payload; links share the installed app's routing contract.

v3 (#116) only ADDS to v2: every v2 key keeps its name and meaning, so a v2 app that ignores
unknown keys is unaffected. New: `channel` (always) and `category` (only when a safe action
set applies, see `push_categories`). Titles and bodies are clamped for watch screens.
"""

from apps.integrations.mobile_link_contract import is_supported_link
from apps.integrations.push_categories import category_for, channel_for

PAYLOAD_VERSION = "3"
TITLE_LIMIT = 40
BODY_LIMIT = 120
ELLIPSIS = "…"


def shorten(text, limit):
    """Collapse whitespace and cut at a word boundary, ellipsis included in `limit`."""
    text = " ".join(str(text or "").split())
    if len(text) <= limit:
        return text
    cut = text[:limit - 1]
    space = cut.rfind(" ")
    # A single very long word is hard-cut rather than reduced to almost nothing.
    if space >= limit // 2:
        cut = cut[:space]
    return cut.rstrip(" ,.;:-") + ELLIPSIS


def short_title(text):
    return shorten(text, TITLE_LIMIT)


def short_body(text):
    return shorten(text, BODY_LIMIT)


def push_data(*, event_id, makerspace_id, feature, event, inbox_row_id=None, link="", makerspace=None):
    from apps.notifications.inbox import safe_link

    data = {"v": PAYLOAD_VERSION, "event_id": str(event_id), "makerspace_id": str(makerspace_id),
            "feature": str(feature), "event": str(event)}
    if inbox_row_id is not None:
        data["inbox_row_id"] = str(inbox_row_id)
    link = safe_link(link) if isinstance(link, str) else ""
    if link and is_supported_link(link):
        data["link"] = link
    data["channel"] = channel_for(data["feature"], data["event"])
    if makerspace is None:
        from apps.makerspaces.models import Makerspace
        makerspace = Makerspace.objects.filter(pk=makerspace_id).first()
    category = category_for(makerspace, data["feature"], data["event"],
                            has_inbox_row=inbox_row_id is not None)
    if category:
        data["category"] = category
    return data

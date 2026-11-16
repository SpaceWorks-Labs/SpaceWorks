"""Shared subscription bearer path recognition; no separable domain imports.

Release 2 L18 adds the personal shift and combined feeds (`calendar/shifts`, `calendar/mine`).
"""
import re

_FEED_BEARER_PATH = re.compile(
    r"^/api/v1/(?:public/[^/]+/(?:event-calendar|bookings/calendar|calendar/shifts|calendar/mine)|"
    r"admin/makerspaces/[0-9]+/maintenance/feed)/[^/]+\.ics$"
)


def is_calendar_feed_bearer_path(value):
    return bool(_FEED_BEARER_PATH.fullmatch(value or ""))

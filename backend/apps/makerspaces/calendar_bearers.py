"""Shared subscription bearer path recognition; no separable domain imports."""
import re

_FEED_BEARER_PATH = re.compile(
    r"^/api/v1/(?:public/[^/]+/(?:event-calendar|bookings/calendar)|"
    r"admin/makerspaces/[0-9]+/maintenance/feed)/[^/]+\.ics$"
)


def is_calendar_feed_bearer_path(value):
    return bool(_FEED_BEARER_PATH.fullmatch(value or ""))

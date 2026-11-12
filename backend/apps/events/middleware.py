import re

from django.utils.cache import patch_vary_headers


_PRIVATE_EVENT_ROUTES = frozenset({
    "public-event-organization-eligibility", "member-collaborative-events",
})


def private_event_response(request, response):
    """Apply privacy to success AND errors without overriding DRF auth hooks."""
    match = getattr(request, "resolver_match", None)
    if match and match.view_name in _PRIVATE_EVENT_ROUTES:
        response["Cache-Control"] = "private, no-store"
        patch_vary_headers(response, ("Cookie", "Authorization"))
    return response


_FEED_PATH = re.compile(
    r"(/api/v1/(?:public/[^/\s]+/(?:event-calendar|bookings/calendar|calendar/shifts|calendar/mine)|"
    r"admin/makerspaces/[0-9]+/maintenance/feed)/)[^/?\s]+(\.ics)"
)
# Compatibility export; shared HMAC infrastructure imports the core helper.
from apps.makerspaces.calendar_bearers import is_calendar_feed_bearer_path


# Decision 335(d): the deprecated display-screen poll still carries the screen's secret in its path.
_DISPLAY_PATH = re.compile(r"(/api/v1/space-displays/)[^/?\s]+(/state/)")


def redact_calendar_feed_uri(value):
    return _FEED_PATH.sub(r"\1[redacted]\2", value or "")


def redact_bearer_uri(value):
    """Every path-borne bearer this middleware hides: calendar feeds and display-screen secrets."""
    return _DISPLAY_PATH.sub(r"\1[redacted]\2", redact_calendar_feed_uri(value))


class CalendarFeedLogRedactionMiddleware:
    """Remove bearer feed and display-screen tokens from WSGI/Gunicorn request-line logging."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        from apps.integrations.notification_media_secrets import redact_media_uri
        raw_uri = request.META.get("RAW_URI")
        if raw_uri:
            request.META["RAW_URI"] = redact_media_uri(redact_bearer_uri(raw_uri))
        feed_path = request.path_info if (is_calendar_feed_bearer_path(request.path_info)
            or redact_bearer_uri(request.path_info) != request.path_info
            or redact_media_uri(request.path_info) != request.path_info) else None
        try:
            response = private_event_response(request, self.get_response(request))
            if redact_media_uri(request.path_info) != request.path_info:
                response["Cache-Control"] = "private, no-store"
            return response
        finally:
            # Resolution and the view need the real token. Access/error logging happens
            # after the response, so replace every request-line source only on unwind.
            if feed_path:
                redacted = redact_media_uri(redact_bearer_uri(feed_path))
                request.path = redacted
                request.path_info = redacted
                request.META["PATH_INFO"] = redacted

"""WhatsApp sessions are opened by authenticated inbound traffic only."""
from datetime import datetime, timedelta, timezone as datetime_timezone

from django.utils import timezone

MAX_SKEW_SECONDS = 300


def in_session_window(endpoint, *, now=None):
    now = now or timezone.now()
    inbound = endpoint.last_inbound_at
    return bool(inbound and now - timedelta(hours=24) < inbound <= now)


def inbound_time(value, *, now=None):
    """Use provider event time, never receipt time: retries cannot renew a session."""
    now = now or timezone.now()
    if not isinstance(value, str) or not value.isascii() or not value.isdigit() or len(value) > 12:
        return None
    try:
        moment = datetime.fromtimestamp(int(value), tz=datetime_timezone.utc)
    except (ValueError, OverflowError, OSError):
        return None
    # Tolerate small provider/host clock skew (clamped to now); never a future window.
    if moment > now + timedelta(seconds=MAX_SKEW_SECONDS):
        return None
    return min(moment, now)

"""Provider event time is optional; receipt/observation time never substitutes for it."""
from datetime import datetime, timedelta, timezone as dt_timezone

from django.utils import timezone

from .messaging.webhook_payloads import timestamp


def provider_time(value):
    try:
        normalized = timestamp(value)
        moment = datetime.fromtimestamp(int(normalized), tz=dt_timezone.utc) if normalized is not None else None
    except (ValueError, TypeError, OverflowError, OSError):
        return None
    if moment and 0 <= moment.timestamp() and moment <= timezone.now() + timedelta(minutes=5):
        return moment
    return None

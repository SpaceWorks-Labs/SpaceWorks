"""Event-day projection uses current attendance and immutable check-in evidence."""

from datetime import timedelta

from django.db.models import Count, Max
from django.utils import timezone

from apps.events import event_authority
from apps.events.event_permissions import CHECK_IN
from apps.events.models_attendance import EventCheckInEvent
from .aggregate import aggregate


BUCKET = timedelta(minutes=15)
MAX_BUCKETS = 96


def attendance_times(event, *, since=None, until=None):
    # Undo retains evidence; exclude registrations whose current state is no longer attended.
    rows = EventCheckInEvent.objects.filter(event=event, registration__event=event,
                                           registration__status="attended")
    rows = rows.values("registration_id").annotate(at=Max("attended_at"))
    if since is not None:
        rows = rows.filter(at__gte=since)
    if until is not None:
        rows = rows.filter(at__lt=until)
    return rows


def project_live(event, *, actor, now=None):
    event_authority.require(actor, event, CHECK_IN)
    envelope = aggregate(event, actor)
    now = now or timezone.now()
    available_from = event.starts_at - timedelta(hours=2)
    counts = dict(event.registrations.values_list("status").annotate(n=Count("pk")))
    # At most one day of buckets. Keep bucket boundaries relative to doors, independent of DST.
    end = min(now, event.ends_at)
    offset = max(0, int((end - available_from) / BUCKET))
    first = max(0, offset - MAX_BUCKETS + 1)
    buckets = [{"starts_at": available_from + index * BUCKET, "count": 0}
               for index in range(first, offset + 1)] if end >= available_from else []
    if buckets:
        for row in attendance_times(event, since=buckets[0]["starts_at"], until=end + timedelta(microseconds=1)):
            index = int((row["at"] - available_from) / BUCKET) - first
            if 0 <= index < len(buckets):
                buckets[index]["count"] += 1
    checked_in = counts.get("attended", 0)
    return {**envelope, "generated_at": now, "available_from": available_from,
            "doors_open_at": event.starts_at, "seconds_until_doors": max(0, int((event.starts_at - now).total_seconds())),
            "active": available_from <= now <= event.ends_at,
            "going": counts.get("registered", 0) + checked_in, "checked_in": checked_in,
            "arrivals": buckets, "first_run": checked_in == 0 and not EventCheckInEvent.objects.filter(event=event).exists()}

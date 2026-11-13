"""Anonymous, allow-listed "now" projections shared by the public page and paired displays (307a).

Machines say only WHAT is in use, never who: no session, user, job or booking row is read. The
calendar lists only events the public listing already shows (`events.website_visibility.listed_events`):
published, listed and not yet over, so a finished event never reappears on a screen (L-D4).
"""
from datetime import datetime, time, timedelta

from django.utils import timezone

from apps.events.website_visibility import listed_events
from apps.machines.models import Machine
from apps.makerspaces.platform import module_enabled

IN_USE = {Machine.Status.RUNNING, Machine.Status.RESERVED}
OUT_OF_SERVICE = {Machine.Status.MAINTENANCE, Machine.Status.OFFLINE}
MAX_MACHINES = 60
MAX_EVENTS = 200
MIN_YEAR, MAX_YEAR = 2000, 2100  # L-D4: a far-off month (9999-12) overflowed date arithmetic into a 500


def _bucket(status):
    if status in IN_USE:
        return "in_use"
    return "out_of_service" if status in OUT_OF_SERVICE else "free"


def machines_now(space):
    """`None` while the machines module is off (the caller then omits the panel)."""
    if not module_enabled(space, "machines"):
        return None
    rows = Machine.objects.filter(makerspace=space, is_public=True, is_active=True).select_related(
        "machine_type").order_by("name", "pk")[:MAX_MACHINES]
    items = [{"name": m.name, "type": m.machine_type.name, "status": _bucket(m.status)} for m in rows]
    counts = {key: sum(1 for i in items if i["status"] == key) for key in ("in_use", "free", "out_of_service")}
    return {**counts, "items": items}


def parse_month(value, today):
    """The first day of a `YYYY-MM` month inside MIN_YEAR..MAX_YEAR; anything else is this month."""
    try:
        year, month = (int(part) for part in str(value).split("-", 1))
        if MIN_YEAR <= year <= MAX_YEAR:
            return datetime(year, month, 1).date()
    except (TypeError, ValueError):
        pass
    return today.replace(day=1)


def calendar_events(space, month=None, *, now=None):
    """`None` while the events module is off; else `{month, events, live}` for public, listed events."""
    if not module_enabled(space, "events"):
        return None
    now = now or timezone.now()
    first = parse_month(month, timezone.localdate(now))
    start = timezone.make_aware(datetime.combine(first, time.min))
    end = timezone.make_aware(datetime.combine((first + timedelta(days=32)).replace(day=1), time.min))
    rows = (listed_events(space).filter(starts_at__lt=end, ends_at__gte=start)
            .order_by("starts_at", "pk")[:MAX_EVENTS])
    events = [{"token": str(e.public_token), "title": e.title, "starts_at": e.starts_at.isoformat(),
               "ends_at": e.ends_at.isoformat(), "location": e.location,
               "delivery_mode": e.delivery_mode, "live": e.starts_at <= now <= e.ends_at} for e in rows]
    return {"month": first.strftime("%Y-%m"), "events": events,
            "live": [e for e in events if e["live"]]}

"""Ledger `?due=today|soon`: the same windows as the dashboard's due_today_loans / due_soon_loans counters."""

from datetime import datetime, time, timedelta

from django.utils import timezone

from apps.makerspaces.local_time import local_day_bounds, to_local
from apps.makerspaces.models import Makerspace
from apps.operations.dashboard_due_back import SOON_DAYS


def due_window(makerspace_id, name):
    """UTC `[low, high)` for `today` (rest of the local day) or `soon` (the next SOON_DAYS days), else None."""
    if name not in ("today", "soon"):
        return None
    space = Makerspace.objects.filter(pk=makerspace_id).first() if makerspace_id else None
    now = timezone.now()
    if space is None:  # the superadmin all-spaces view has no single local day; use the active zone
        today = timezone.localdate(now)
        start = timezone.make_aware(datetime.combine(today, time.min))
        tomorrow = start + timedelta(days=1)
        horizon = tomorrow + timedelta(days=SOON_DAYS)
    else:
        today = to_local(space, now).date()
        start = local_day_bounds(space, today)[0]
        tomorrow = local_day_bounds(space, today + timedelta(days=1))[0]
        horizon = local_day_bounds(space, today + timedelta(days=1 + SOON_DAYS))[0]
    return (max(start, now), tomorrow) if name == "today" else (tomorrow, horizon)

"""Bounded, query-derived daily counts. No source title, link or time is returned."""

from django.utils.translation import gettext
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from .platform import module_enabled
from .profile_activity_sources import FAMILY_CONSENTS, activity_sources


def activity_window(profile, params):
    tz = ZoneInfo(profile.membership.makerspace.timezone)
    today = timezone.now().astimezone(tz).date()
    try:
        end = date.fromisoformat(params.get("to", today.isoformat()))
        start = date.fromisoformat(params.get("from", (end - timedelta(days=119)).isoformat()))
        if end < start or (end - start).days >= 120 or end > today or end == date.max:
            raise ValueError
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValidationError({"window": gettext("Use ISO dates, from <= to <= today, at most 120 inclusive days.")}) from exc
    return start, end, tz


def daily_activity(profile, params):
    start, end, tz = activity_window(profile, params)
    payload = {"from": start, "to": end, "timezone": str(tz), "days": []}
    if not profile.show_activity_graph:
        return payload
    buckets = {}
    day = start
    while day <= end:
        buckets[day] = {"date": day, "count": 0, "families": {}}
        day += timedelta(days=1)
    lower = datetime.combine(start, time.min, tzinfo=tz)
    upper = datetime.combine(end + timedelta(days=1), time.min, tzinfo=tz)
    for source in activity_sources():
        if not getattr(profile, FAMILY_CONSENTS[source.family]) or not module_enabled(
            profile.membership.makerspace, source.module
        ):
            continue
        seen = set()
        for milestone in source.milestones(profile, lower, upper):
            day = milestone.occurred_at.astimezone(tz).date()
            identity = (milestone.record, day)
            if day not in buckets or identity in seen:
                continue
            seen.add(identity)
            bucket = buckets[day]
            bucket["count"] += 1
            bucket["families"][source.family] = bucket["families"].get(source.family, 0) + 1
    payload["days"] = list(buckets.values())
    return payload

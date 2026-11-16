"""Bounded, query-derived daily counts for the GLOBAL profile. No source title, link or time is returned.

Account-level (decision 304c): each registered source runs once per space the person is an active
member of (`account_profile_spaces.listed_memberships`) whose module is on, through a small
`SpaceScope` that gives the existing per-membership sources the `.membership` / `.projects` they
expect. A milestone is deduplicated by (record, local day) across spaces; record ids are
model-qualified so two spaces can never collide. Consent is per family on the account profile.
"""

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from django.utils import timezone
from django.utils.translation import gettext
from rest_framework.exceptions import ValidationError

from .account_profile_spaces import listed_memberships
from .platform import module_enabled
from .profile_activity_sources import FAMILY_CONSENTS, activity_sources


class SpaceScope:
    """One space's view of the account profile, for sources written against a membership profile."""

    def __init__(self, account, membership):
        self.account, self.membership = account, membership
        self.projects = account.projects

    def __getattr__(self, name):
        return getattr(self.account, name)


def _timezone(account):
    from .profile_images import home_space

    space = home_space(account.user)
    return ZoneInfo(space.timezone) if space is not None else ZoneInfo("UTC")


def activity_window(account, params):
    tz = _timezone(account)
    today = timezone.now().astimezone(tz).date()
    try:
        end = date.fromisoformat(params.get("to", today.isoformat()))
        start = date.fromisoformat(params.get("from", (end - timedelta(days=119)).isoformat()))
        if end < start or (end - start).days >= 120 or end > today or end == date.max:
            raise ValueError
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValidationError({"window": gettext("Use ISO dates, from <= to <= today, at most 120 inclusive days.")}) from exc
    return start, end, tz


def scopes_for(account):
    seen, scopes = set(), []
    for membership in listed_memberships(account.user):
        if membership.makerspace_id not in seen:
            seen.add(membership.makerspace_id)
            scopes.append(SpaceScope(account, membership))
    return scopes


def daily_activity(account, params):
    start, end, tz = activity_window(account, params)
    payload = {"from": start, "to": end, "timezone": str(tz), "days": []}
    if not account.show_activity_graph:
        return payload
    buckets = {}
    day = start
    while day <= end:
        buckets[day] = {"date": day, "count": 0, "families": {}}
        day += timedelta(days=1)
    lower = datetime.combine(start, time.min, tzinfo=tz)
    upper = datetime.combine(end + timedelta(days=1), time.min, tzinfo=tz)
    scopes = scopes_for(account)
    for source in activity_sources():
        if not getattr(account, FAMILY_CONSENTS[source.family]):
            continue
        seen = set()
        for scope in scopes:
            if not module_enabled(scope.membership.makerspace, source.module):
                continue
            for milestone in source.milestones(scope, lower, upper):
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

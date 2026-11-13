"""Web and app use: which client people reach the system from, and what they use it for.

Two measures, both counts only (no person, session, address or user agent leaves the database):

* ``session_days`` -- distinct sessions active per local day, by channel (``web`` from
  ``WebSessionActivityDay``; ``ios`` / ``android`` from ``DeviceActivityDay``). Week and month
  periods sum these session-days.
* ``active_accounts`` / ``new_accounts`` / ``returning_accounts`` -- distinct people active per channel and
  period, split by whether their first recorded day on that channel falls in the period (counts only).
* ``app_versions`` -- distinct app installs per platform and build (``area`` = version), from the optional
  ``X-SpaceWorks-App-Version`` header; ``flow_completions`` -- successful key flows (``area`` = flow) per channel.
* ``api_calls`` -- authenticated API calls per channel and *area* (the app that serves the route),
  from ``ChannelUsageDay``; ``api_client`` (signed clients, access tokens) appears only here.

The phone channels belong to the ``mobile`` module and are hidden for a space that has it off.
``share_percent`` is each row's share of its (makerspace, period, measure) total.
"""

from collections import defaultdict
from datetime import timedelta

from apps.accounts.models_activity import ChannelUsageDay, DeviceActivityDay, WebSessionActivityDay
from apps.makerspaces.module_registry import module_available
from apps.makerspaces.platform import module_enabled
from apps.makerspaces.servability import servable_queryset
from apps.operations.platform_scope import platform_analytics_spaces, require_platform_context
from apps.operations.report_fields_channels import CHANNEL_USAGE_FIELDS as FIELDS
from apps.operations.report_channel_sources import visible_area
from apps.operations.report_types import ReportNotFound, ReportResult
from apps.operations.reports_common import limited
from apps.operations.reports_j_common import area_spaces, calendar_range, rate

PHONE = {"apple": "ios", "android": "android"}
DEFINITION = ("Distinct sessions per local day by channel (web, ios, android), distinct and new or returning active accounts, "
              "app builds, key flows completed and authenticated API calls by channel (web, ios, android, api_client) and app area. "
              "Week and month periods sum session-days.")
LIMITATIONS = ("Counts only. Recording started with this release, so earlier days are empty. Web and app session-days "
               "are recorded once per session, space and day; a person active in several spaces counts in each space "
               "(once in the platform total). Call and flow counts are approximate. App builds need the app to send its version. "
               "Payment flows count checkouts started; settlement arrives by an outside notification and has no channel. "
               "Phone channels need the mobile module. "
               "Signed API clients and personal access grants appear as api_client calls only.")


def _period(day, grain):
    if grain == "week":
        day -= timedelta(days=day.weekday())
    elif grain == "month":
        day = day.replace(day=1)
    elif grain != "day":
        raise ValueError("Unsupported report grain.")
    return day.isoformat()


def _in_range(qs, field, date_range):
    for bound, lookup in zip(date_range or (None, None), ("gte", "lt")):
        if bound is not None:
            qs = qs.filter(**{f"{field}__{lookup}": bound.date()})
    return qs


def _scoped(qs, space_ids, include_null):
    from django.db.models import Q
    return qs.filter(Q(makerspace_id__in=space_ids) | (Q(makerspace__isnull=True) if include_null else Q(pk__in=[])))


def collect(spaces, *, include_null, date_range, grain):
    """Counters keyed ``(space_id, period, measure, channel, area)`` over the given spaces.

    Accounts, versions and sessions are worked out privately here (user and grant ids never leave);
    only the counts are returned."""
    ids = [space.pk for space in spaces]
    phone_ids = [space.pk for space in spaces if module_available("mobile") and module_enabled(space, "mobile")]
    out = defaultdict(int)
    sessions, people, builds = {}, {}, {}
    web = _in_range(_scoped(WebSessionActivityDay.objects.all(), ids, include_null), "local_day", date_range)
    for row in web.order_by("local_day", "makerspace_id").values("local_day", "session_hash", "user_id", "makerspace_id").iterator():
        sessions.setdefault(("web", row["local_day"], row["session_hash"]), row["makerspace_id"])
        people.setdefault(("web", _period(row["local_day"], grain), row["user_id"]), row["makerspace_id"])
    phone = _in_range(_scoped(DeviceActivityDay.objects.all(), phone_ids, include_null and module_available("mobile")), "local_day", date_range)
    for row in phone.order_by("local_day", "makerspace_id").values(
            "local_day", "platform", "grant_id", "grant__user_id", "app_version", "makerspace_id").iterator():
        channel = PHONE.get(row["platform"])
        if not channel:
            continue
        sessions.setdefault((channel, row["local_day"], row["grant_id"]), row["makerspace_id"])
        people.setdefault((channel, _period(row["local_day"], grain), row["grant__user_id"]), row["makerspace_id"])
        builds.setdefault((channel, _period(row["local_day"], grain), row["grant_id"]), (row["makerspace_id"], row["app_version"] or "unknown"))
    for (channel, day, _who), space_id in sessions.items():
        out[(space_id, _period(day, grain), "session_days", channel, "all")] += 1
    first = _first_days(ids, phone_ids, include_null, grain)
    for (channel, period, user), space_id in people.items():
        kind = "new_accounts" if first.get((channel, user)) == period else "returning_accounts"
        out[(space_id, period, "active_accounts", channel, "all")] += 1
        out[(space_id, period, kind, channel, "all")] += 1
    for (channel, period, _grant), (space_id, version) in builds.items():
        out[(space_id, period, "app_versions", channel, version)] += 1
    calls = _in_range(_scoped(ChannelUsageDay.objects.all(), ids, include_null), "day", date_range)
    by_id = {space.pk: space for space in spaces}
    for row in calls.values("makerspace_id", "day", "channel", "area", "count").iterator():
        if row["channel"] in ("ios", "android") and (not module_available("mobile") or (
                row["makerspace_id"] is not None and row["makerspace_id"] not in phone_ids)):
            continue
        if row["makerspace_id"] is not None and not visible_area(by_id[row["makerspace_id"]], row["area"]):
            continue
        flow = row["area"].startswith("flow:")
        out[(row["makerspace_id"], _period(row["day"], grain), "flow_completions" if flow else "api_calls",
             row["channel"], row["area"][5:] if flow else row["area"])] += row["count"]
    return out


def _first_days(ids, phone_ids, include_null, grain):
    """The period of each person's first recorded day per channel (history starts with this release)."""
    from django.db.models import Min
    first = {}
    for row in _scoped(WebSessionActivityDay.objects.all(), ids, include_null).values("user_id").annotate(day=Min("local_day")):
        first[("web", row["user_id"])] = _period(row["day"], grain)
    phone = _scoped(DeviceActivityDay.objects.all(), phone_ids, include_null and module_available("mobile"))
    for row in phone.values("platform", "grant__user_id").annotate(day=Min("local_day")):
        if row["platform"] in PHONE:
            first[(PHONE[row["platform"]], row["grant__user_id"])] = _period(row["day"], grain)
    return first


def rows_for(counters, *, with_space):
    totals = defaultdict(int)
    for (space_id, period, measure, channel, area), value in counters.items():
        totals[_share_group(space_id, period, measure, channel, area)] += value
    rows = []
    for (space_id, period, measure, channel, area), value in counters.items():
        row = {"period": period, "measure": measure, "channel": channel, "area": area, "value": value,
               "share_percent": rate(value, totals[_share_group(space_id, period, measure, channel, area)])}
        rows.append({"makerspace_id": space_id, **row} if with_space else row)
    rows.sort(key=lambda r: (r["period"], r.get("makerspace_id") or 0, r["measure"], -r["value"], r["channel"], r["area"]))
    return rows


def _share_group(space_id, period, measure, channel, area):
    """Flows share across channels per flow; builds share within their channel; the rest across channels."""
    if measure == "flow_completions":
        return (space_id, period, measure, area)
    if measure == "app_versions":
        return (space_id, period, measure, channel)
    return (space_id, period, measure)


def build_channel_usage(makerspace_id=None, *, limit=None, date_range=None, grain="day", actor=None):
    """Space report: one makerspace (or each eligible one for a deployment roll-up)."""
    records = []
    for space in area_spaces(makerspace_id, "reports"):
        counters = collect([space], include_null=False, date_range=calendar_range(date_range, space), grain=grain)
        records.extend(rows_for(counters, with_space=makerspace_id is None))
    fields = FIELDS if makerspace_id is not None else ("makerspace_id", *FIELDS)
    return ReportResult(fields, limited(records, limit), {"definition": DEFINITION, "limitations": LIMITATIONS})


def build_platform_channel_usage(makerspace_id=None, *, platform_context=None, limit=None, date_range=None, grain="day"):
    ctx = require_platform_context(platform_context)
    if makerspace_id is not None:
        raise ReportNotFound()
    spaces = list(servable_queryset(platform_analytics_spaces(ctx)).order_by("pk"))
    counters = collect(spaces, include_null=True, date_range=calendar_range(date_range), grain=grain)
    return ReportResult(("makerspace_id", *FIELDS), limited(rows_for(counters, with_space=True), limit),
                        {"definition": DEFINITION, "limitations": LIMITATIONS,
                         "space_ids": [space.pk for space in spaces if module_enabled(space, "reports")]})

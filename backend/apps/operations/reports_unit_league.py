"""Unit league and level league: counts per member unit (parity O-B3, An3).

COUNTS ONLY -- no member is named and no money is shown, so a unit's figures can sit beside every other unit's
without exposing anyone across units. Needs `membership.units` (the report is refused while it is off).

* Unit league: one row per unit -- active members in the unit's WHOLE subtree (`members`), those placed directly
  in it (`direct_members`), memberships created inside the window (`joined`) and join requests still waiting
  (`pending_requests`, subtree). Biggest first.
* Level league: one row per level ("District", "Chapter", ...) -- how many units sit on it and the members placed
  directly on those units, so the levels sum to the space's placed members.

A unit-scoped actor (`member_unit_scope`) sees only the units inside their own subtree; the level league is
computed over those units alone. Members with no unit are in neither league. Archived units are left out.
"""

from collections import Counter

from apps.operations.report_types import ReportResult
from apps.operations.reports_finance_sources import finance_window

UNIT_FIELDS = ("unit_id", "unit_code", "unit_name", "level", "level_name", "parent_code", "members",
               "direct_members", "joined", "pending_requests")
LEVEL_FIELDS = ("level", "level_name", "units", "members", "joined", "pending_requests")
PENDING_STATES = ("requested", "awaiting_vouches", "awaiting_payment", "changes_requested")


def _ancestors(path):
    codes = [part for part in path.split("/") if part]
    return ["/" + "/".join(codes[:index + 1]) + "/" for index in range(len(codes))]


def _rollup(paths):
    totals = Counter()
    for path, count in paths.items():
        for prefix in _ancestors(path):
            totals[prefix] += count
    return totals


def _tallies(space, actor, date_range):
    """`(units, direct, joined, pending)` -- the visible units and per-unit-path counters."""
    from apps.makerspaces.member_unit_scope import narrow_by_unit_lookup
    from apps.makerspaces.models import MembershipRequest
    from apps.makerspaces.models_member_units import MemberUnit, MembershipUnit

    units = list(narrow_by_unit_lookup(
        MemberUnit.objects.filter(makerspace=space, archived_at__isnull=True), actor, space.pk, "path",
        "manage_members").select_related("parent"))
    start, end = finance_window(space, date_range)
    placed = MembershipUnit.objects.filter(makerspace=space, membership__status="active",
                                           membership__track="community")
    direct = Counter(placed.values_list("unit__path", flat=True))
    joined_rows = placed
    if start is not None:
        joined_rows = joined_rows.filter(membership__created_at__gte=start)
    if end is not None:
        joined_rows = joined_rows.filter(membership__created_at__lt=end)
    joined = Counter(joined_rows.values_list("unit__path", flat=True))
    waiting = MembershipRequest.objects.filter(makerspace=space, kind="request", state__in=PENDING_STATES,
                                               unit_choice__isnull=False)
    pending = Counter(waiting.values_list("unit_choice__unit__path", flat=True))
    return units, direct, joined, pending


def _names(space):
    from apps.makerspaces.member_units import level_names

    names = level_names(space)
    return lambda level: names[level] if level < len(names) else ""


def build_unit_league(makerspace_id, *, limit=None, date_range=None, actor=None, **_ignored):
    from apps.makerspaces.models import Makerspace

    space = Makerspace.objects.get(pk=makerspace_id)
    units, direct, joined, pending = _tallies(space, actor, date_range)
    members, joined_total, pending_total = _rollup(direct), _rollup(joined), _rollup(pending)
    level_name = _names(space)
    records = [{"unit_id": unit.pk, "unit_code": unit.code, "unit_name": unit.name, "level": unit.level,
                "level_name": level_name(unit.level), "parent_code": unit.parent.code if unit.parent_id else "",
                "members": members[unit.path], "direct_members": direct[unit.path],
                "joined": joined_total[unit.path], "pending_requests": pending_total[unit.path]}
               for unit in units]
    records.sort(key=lambda row: (-row["members"], row["unit_name"], row["unit_id"]))
    return ReportResult(UNIT_FIELDS, records if limit is None else records[:limit], {
        "definition": "Active members per unit (the unit and everything beneath it), members placed directly in "
                      "it, memberships created in the window and join requests still waiting. Counts only; "
                      "members without a unit are not counted."})


def build_level_league(makerspace_id, *, limit=None, date_range=None, actor=None, **_ignored):
    from apps.makerspaces.models import Makerspace

    space = Makerspace.objects.get(pk=makerspace_id)
    units, direct, joined, pending = _tallies(space, actor, date_range)
    level_name, levels = _names(space), {}
    for unit in units:
        row = levels.setdefault(unit.level, {"level": unit.level, "level_name": level_name(unit.level),
                                             "units": 0, "members": 0, "joined": 0, "pending_requests": 0})
        row["units"] += 1
        row["members"] += direct[unit.path]
        row["joined"] += joined[unit.path]
        row["pending_requests"] += pending[unit.path]
    records = [levels[level] for level in sorted(levels)]
    return ReportResult(LEVEL_FIELDS, records if limit is None else records[:limit], {
        "definition": "Per level of the unit tree: how many units sit on it and the members placed directly on "
                      "them. Counts only."})

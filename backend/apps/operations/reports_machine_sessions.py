"""Machine-session reports (lane L23, #158.6), behind `reports` and `machines.sessions`.

Every builder reads sessions on the machines the actor's role scope covers, in the
report window (default: the last 30 days, ending now). A session counts for the part of
it inside the window; a live one counts up to now. Corrections staff made are applied
(the effective duration and member). Times are bucketed in the space's own timezone.
"""

from collections import defaultdict
from datetime import timedelta
from decimal import Decimal

from django.db.models import Max, Q
from django.utils import timezone

from apps.machines import sessions_state as state
from apps.machines.models import MachineSession
from apps.makerspaces.local_time import next_open_interval, to_local
from apps.makerspaces.opening_hours import has_hours
from .reports_machine_common import hours, machines, result, space_ids, spaces

SESSION_FIELDS = ("session_id", "started_at", "ended_at", "machine_id", "machine_name", "machine_type", "member_id",
                  "member_name", "source", "minutes", "stop_reason", "flagged")
UTILISATION_FIELDS = ("level", "machine_type", "machine_id", "machine_name", "sessions", "busy_hours", "open_hours",
                      "utilisation_percent")
BUSIEST_FIELDS = ("weekday", "hour", "sessions", "busy_hours")
IDLE_FIELDS = ("machine_id", "machine_name", "machine_type", "last_session_at", "idle_days")
FLAGGED_FIELDS = ("session_id", "started_at", "ended_at", "machine_id", "machine_name", "machine_type", "member_id",
                  "member_name", "stop_reason", "minutes", "corrected_minutes", "confirmed")
WEEKDAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")


def window(date_range, now=None):
    now = now or timezone.now()
    start, end = date_range or (None, None)
    end = min(end, now) if end else now
    return start or end - timedelta(days=30), end


def _in_window(space, scope, start, end):
    return MachineSession.objects.filter(
        makerspace_id__in=space_ids(space), machine__in=machines(space, scope), started_at__lt=end,
    ).filter(Q(ended_at__isnull=True) | Q(ended_at__gt=start))


def _sessions(space, scope, start, end):
    return _in_window(space, scope, start, end).select_related(
        "machine", "machine_type", "member").prefetch_related("amendments__member").order_by("started_at", "pk")


def _overlap(row, start, end, now):
    lower, upper = max(row.started_at, start), min(row.ended_at or now, end)
    return (lower, upper) if upper > lower else None


def _minutes(row, now):
    if row.ended_at is None:
        return max(int((now - row.started_at).total_seconds() // 60), 0)
    return state.effective_minutes(row)


def _person(row):
    member = state.effective_member(row)
    return (member.pk, member.display_name or member.username) if member is not None else (None, "")


def build_machine_sessions(makerspace_id, *, limit=None, date_range=None, actor=None, **_kwargs):
    rows, now = [], timezone.now()
    for space, scope in spaces(makerspace_id, ("machines",), actor, identities=True):
        start, end = window(date_range, now)
        for row in _sessions(space, scope, start, end):
            member_id, member_name = _person(row)
            rows.append({"makerspace_id": row.makerspace_id, "session_id": row.pk, "started_at": row.started_at,
                         "ended_at": row.ended_at, "machine_id": row.machine_id, "machine_name": row.machine.name,
                         "machine_type": row.machine_type.name, "member_id": member_id, "member_name": member_name,
                         "source": row.source, "minutes": _minutes(row, now), "stop_reason": row.stop_reason,
                         "flagged": row.flagged})
    return result(SESSION_FIELDS, rows, makerspace_id, limit)


def open_hours(space, start, end):
    """Open hours of the space inside [start, end); always open without recorded hours."""
    if not has_hours(space):
        return hours(end - start)
    total, cursor = Decimal(0), start
    for _ in range(400):
        interval = next_open_interval(space, cursor)
        if interval is None or interval[0] >= end:
            break
        lower, upper = max(interval[0], cursor), min(interval[1], end)
        if upper > lower:
            total += hours(upper - lower)
        cursor = interval[1]
        if cursor >= end:
            break
    return total


def build_machine_session_utilisation(makerspace_id, *, limit=None, date_range=None, actor=None, **_kwargs):
    rows, now = [], timezone.now()
    for space, scope in spaces(makerspace_id, ("machines",), actor):
        start, end = window(date_range, now)
        available = open_hours(space, start, end)
        busy, counts = defaultdict(Decimal), defaultdict(int)
        for row in _sessions(space, scope, start, end):
            span = _overlap(row, start, end, now)
            if span is not None:
                busy[row.machine_id] += hours(span[1] - span[0])
                counts[row.machine_id] += 1
        types = defaultdict(lambda: [0, Decimal(0), Decimal(0)])
        for machine in machines(space, scope).select_related("machine_type").order_by("machine_type__name", "name"):
            share = (busy[machine.pk] / available * 100) if available else Decimal(0)
            rows.append({"makerspace_id": machine.makerspace_id, "level": "machine", "machine_type": machine.machine_type.name,
                         "machine_id": machine.pk, "machine_name": machine.name, "sessions": counts[machine.pk],
                         "busy_hours": busy[machine.pk], "open_hours": available, "utilisation_percent": share})
            bucket = types[machine.machine_type.name]
            bucket[0] += counts[machine.pk]
            bucket[1] += busy[machine.pk]
            bucket[2] += available
        for name, (sessions, busy_hours, open_total) in sorted(types.items()):
            rows.append({"makerspace_id": space.pk, "level": "type", "machine_type": name, "machine_id": None,
                         "machine_name": "", "sessions": sessions, "busy_hours": busy_hours, "open_hours": open_total,
                         "utilisation_percent": (busy_hours / open_total * 100) if open_total else Decimal(0)})
    return result(UTILISATION_FIELDS, rows, makerspace_id, limit,
                  definition="Busy hours (sessions) over the space's open hours in the window.")


def build_machine_session_busiest(makerspace_id, *, limit=None, date_range=None, actor=None, **_kwargs):
    rows, now = [], timezone.now()
    for space, scope in spaces(makerspace_id, ("machines",), actor):
        start, end = window(date_range, now)
        busy, started = defaultdict(Decimal), defaultdict(int)
        for row in _sessions(space, scope, start, end):
            span = _overlap(row, start, end, now)
            if span is None:
                continue
            first = to_local(space, span[0])
            started[(first.weekday(), first.hour)] += 1
            cursor = span[0]
            while cursor < span[1]:
                local = to_local(space, cursor)
                boundary = cursor + timedelta(minutes=60 - local.minute, seconds=-local.second,
                                              microseconds=-local.microsecond)
                upper = min(boundary, span[1])
                busy[(local.weekday(), local.hour)] += hours(upper - cursor)
                cursor = upper
        for (weekday, hour) in sorted(set(busy) | set(started)):
            rows.append({"makerspace_id": space.pk, "weekday": WEEKDAYS[weekday], "hour": hour,
                         "sessions": started[(weekday, hour)], "busy_hours": busy[(weekday, hour)]})
    return result(BUSIEST_FIELDS, rows, makerspace_id, limit)


def build_machine_session_idle(makerspace_id, *, limit=None, date_range=None, actor=None, **_kwargs):
    rows, now = [], timezone.now()
    for space, scope in spaces(makerspace_id, ("machines",), actor):
        start, end = window(date_range, now)
        catalog = machines(space, scope).filter(is_active=True).select_related("machine_type")
        used = set(_in_window(space, scope, start, end).values_list("machine_id", flat=True))
        last = dict(MachineSession.objects.filter(machine__in=catalog).values("machine_id").annotate(
            last=Max("started_at")).values_list("machine_id", "last"))
        for machine in catalog.order_by("machine_type__name", "name"):
            if machine.pk in used:
                continue
            since = last.get(machine.pk) or machine.created_at
            rows.append({"makerspace_id": machine.makerspace_id, "machine_id": machine.pk, "machine_name": machine.name,
                         "machine_type": machine.machine_type.name, "last_session_at": last.get(machine.pk),
                         "idle_days": max((end - since).days, 0)})
    return result(IDLE_FIELDS, rows, makerspace_id, limit,
                  definition="Active machines with no session in the window; idle days count to the window's end.")


def build_machine_session_flagged(makerspace_id, *, limit=None, date_range=None, actor=None, **_kwargs):
    rows, now = [], timezone.now()
    for space, scope in spaces(makerspace_id, ("machines",), actor, identities=True):
        start, end = window(date_range, now)
        for row in _sessions(space, scope, start, end).filter(flagged=True):
            member_id, member_name = _person(row)
            corrected = state.effective_minutes(row)
            rows.append({"makerspace_id": row.makerspace_id, "session_id": row.pk, "started_at": row.started_at,
                         "ended_at": row.ended_at, "machine_id": row.machine_id, "machine_name": row.machine.name,
                         "machine_type": row.machine_type.name, "member_id": member_id, "member_name": member_name,
                         "stop_reason": row.stop_reason, "minutes": row.duration_minutes,
                         "corrected_minutes": corrected if corrected != row.duration_minutes else None,
                         "confirmed": state.confirmed(row)})
    return result(FLAGGED_FIELDS, rows, makerspace_id, limit)

"""Unavailable time for one bookable room: a read-only overlay over the modules that own it.

Three layers, each read from its owner and each absent when that owner is:

* room outages (`maintenance.repairs.room_outages`; gone when `maintenance` is tombstoned),
  in the outage's own block or warn mode;
* the repair window of the machine whose time the room books (`machines.booking_gate`);
* closures: the gaps between `published_open_intervals`, only when the space records hours.

Staff see the layer, its severity and an outage's reason. The public sees only `unavailable`
or `closed`, never a warn-mode outage (it refuses nothing) and never a repair detail; and
`public_busy_blocks` keeps `unavailable` only for a room that shows public availability
(decision 219c) -- `closed` is the published hours and always shows. Nothing here refuses
anything: admission still calls the same seams, this only shows them.
"""

from rest_framework import serializers

ROOM_OUTAGE, MACHINE_REPAIR, CLOSED, UNAVAILABLE = "room_outage", "machine_repair", "closed", "unavailable"
BLOCK, WARN = "block", "warn"


def _clip(start, end, lo, hi):
    start = lo if start is None else max(start, lo)
    end = hi if end is None else min(end, hi)
    return (start, end) if start < end else None


def _block(window, kind, severity, reason="", since=None):
    # `since` is the source row's own start (outage or downtime), only for the feed's stable
    # DTSTAMP (`feed_blocks`); serializers and the public projection never emit it.
    return {"starts_at": window[0], "ends_at": window[1], "kind": kind, "severity": severity, "reason": reason,
            "since": since}


def _room_outage(space, lo, hi):
    from .admission import room_outages_apply
    if not room_outages_apply(space):
        return []
    from apps.maintenance.repairs.room_outages import open_outage
    outage = open_outage(space)
    window = outage and _clip(outage.started_at, outage.expected_back_at, lo, hi)
    if not window:
        return []
    severity = BLOCK if outage.mode == outage.Mode.BLOCK else WARN
    return [_block(window, ROOM_OUTAGE, severity, outage.reason, since=outage.started_at)]


def _machine_time_booking_off(space, lo, hi):
    from .admission import machine_time_booking_off
    return [_block((lo, hi), MACHINE_REPAIR, BLOCK)] if machine_time_booking_off(space) and lo < hi else []


def _machine_repair(space, lo, hi):
    from .admission import machine_repairs_apply
    if not machine_repairs_apply(space):
        return []
    from apps.machines.booking_gate import repair_window
    from apps.machines.models import Machine
    machine = Machine.objects.filter(pk=space.machine_id).only("id", "status").first()
    repair = machine and repair_window(machine)
    window = repair and _clip(repair[0], repair[1], lo, hi)
    return [_block(window, MACHINE_REPAIR, BLOCK, since=repair[0])] if window else []


def _closures(makerspace, lo, hi):
    from apps.makerspaces.opening_hours import has_hours
    if not has_hours(makerspace):
        return []
    from .services_schedule import published_open_intervals
    gaps, cursor = [], lo
    for interval in published_open_intervals(makerspace, lo, hi):
        if interval["starts_at"] > cursor:
            gaps.append(_block((cursor, interval["starts_at"]), CLOSED, BLOCK))
        cursor = max(cursor, interval["ends_at"])
    if cursor < hi:
        gaps.append(_block((cursor, hi), CLOSED, BLOCK))
    return gaps


def _rows(space, starts_at, ends_at, closures):
    rows = (_machine_time_booking_off(space, starts_at, ends_at) + _room_outage(space, starts_at, ends_at)
            + _machine_repair(space, starts_at, ends_at))
    if closures:
        rows += _closures(space.makerspace, starts_at, ends_at)
    rows.sort(key=lambda row: (row["starts_at"], row["kind"]))
    return rows


def feed_blocks(space, starts_at, ends_at):
    """Public-label blocks for a calendar feed, each with `since`: the source row's own start
    (None for closures), so the feed derives a stable DTSTAMP instead of stamping "now"."""
    return [{"starts_at": row["starts_at"], "ends_at": row["ends_at"], "since": row["since"],
             "kind": CLOSED if row["kind"] == CLOSED else UNAVAILABLE}
            for row in _rows(space, starts_at, ends_at, True) if row["severity"] == BLOCK]


def busy_blocks(space, starts_at, ends_at, *, staff, closures=True):
    """Unavailable windows meeting [starts_at, ends_at), clipped to it and sorted by start."""
    rows = _rows(space, starts_at, ends_at, closures)
    if staff:
        return rows
    return [{"starts_at": row["starts_at"], "ends_at": row["ends_at"],
             "kind": CLOSED if row["kind"] == CLOSED else UNAVAILABLE}
            for row in rows if row["severity"] == BLOCK]


def public_busy_blocks(space, starts_at, ends_at, *, closures=True):
    """Public blocks, with `unavailable` dropped unless the room shows public availability."""
    rows = busy_blocks(space, starts_at, ends_at, staff=False, closures=closures)
    if space.show_public_availability:
        return rows
    return [row for row in rows if row["kind"] == CLOSED]


def venue_update_pending(space, starts_at, ends_at):
    """True when the room is out of service during any part of [starts_at, ends_at); no detail."""
    return bool(busy_blocks(space, starts_at, ends_at, staff=False, closures=False))


class StaffBusyBlockSerializer(serializers.Serializer):
    starts_at = serializers.DateTimeField()
    ends_at = serializers.DateTimeField()
    kind = serializers.ChoiceField(choices=[ROOM_OUTAGE, MACHINE_REPAIR, CLOSED], help_text=(
        "`room_outage` the room is out of service; `machine_repair` the machine this room books is "
        "under repair; `closed` outside the space's opening hours."))
    severity = serializers.ChoiceField(choices=[BLOCK, WARN], help_text=(
        "`block` refuses new bookings in the window; `warn` is a warn-mode room outage that does not."))
    reason = serializers.CharField(allow_blank=True, help_text="The outage reason staff recorded, else empty.")


class PublicBusyBlockSerializer(serializers.Serializer):
    starts_at = serializers.DateTimeField(read_only=True)
    ends_at = serializers.DateTimeField(read_only=True)
    kind = serializers.ChoiceField(choices=[UNAVAILABLE, CLOSED], read_only=True, help_text=(
        "`closed` outside opening hours; `unavailable` for any other reason, never detailed."))

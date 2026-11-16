"""Read-only conflicts between an event's linked reservations and their room's state (decision 216).

A linked room or machine booking keeps its time, status and charge when the room is later taken
out of service, the machine goes for repair or the space's hours change. Nothing here refuses,
cancels or moves anything: each conflict is read from `bookings.busy_overlay`, which reads every
layer from its owner and drops a layer when that owner is off (room outages need
`room_outages_apply`, a repair window `machine_repairs_apply`, closures recorded opening hours).

* `room_out_of_service` (block) and `machine_under_repair` (block): the room or machine would
  refuse a new booking for that time;
* `room_outage_warning` (warning): a warn-mode outage, which refuses nothing;
* `space_closed` (warning): the time falls outside opening hours or on a closure day. Never a
  refusal, because staff events may run after hours.

Only a viewer holding `manage_reservations` on the room or `set_service_state` in the space sees
the outage's window and recorded reason; anyone else gets the code and severity alone.
"""

from django.utils import timezone
from rest_framework import serializers

LIVE = ("pending", "confirmed")
BLOCK, WARNING = "block", "warning"
CODES = ["room_out_of_service", "room_outage_warning", "machine_under_repair", "space_closed"]
MAX_CONFLICTS = 20


def _code(row):
    from apps.bookings.busy_overlay import CLOSED, MACHINE_REPAIR, ROOM_OUTAGE
    if row["kind"] == ROOM_OUTAGE:
        return ("room_out_of_service", BLOCK) if row["severity"] == BLOCK else ("room_outage_warning", WARNING)
    if row["kind"] == MACHINE_REPAIR:
        return "machine_under_repair", BLOCK
    return ("space_closed", WARNING) if row["kind"] == CLOSED else (None, None)


def may_see_detail(actor, space):
    from apps.accounts import rbac
    from apps.bookings import booking_authority, booking_permissions
    return (booking_authority.can(actor, space, booking_permissions.MANAGE_RESERVATIONS)
            or rbac.can(actor, rbac.Action.SET_SERVICE_STATE, space.makerspace_id))


def conflicts(actor, booking, starts_at, ends_at, *, closures=True):
    """Conflicts over [starts_at, ends_at) for a live booking's room; empty when nothing applies."""
    if (booking is None or booking.status not in LIVE or not starts_at or not ends_at
            or ends_at <= max(starts_at, timezone.now())):
        return []
    from apps.bookings.busy_overlay import busy_blocks
    space = booking.space
    lo = max(starts_at, timezone.now())
    detail = may_see_detail(actor, space)
    rows = []
    for row in busy_blocks(space, lo, ends_at, staff=True, closures=closures):
        code, severity = _code(row)
        if code is None:
            continue
        item = {"code": code, "severity": severity}
        if detail:
            item.update(starts_at=row["starts_at"], ends_at=row["ends_at"], reason=row.get("reason", ""))
        rows.append(item)
    if not detail:  # generic viewers learn only that a kind of conflict exists, once
        rows = [dict(pair) for pair in dict.fromkeys(tuple(sorted(row.items())) for row in rows)]
    return rows[:MAX_CONFLICTS]


def event_room_conflicts(actor, event, booking):
    """The event's own window against its current room reservation (draft/published events only)."""
    if event.status not in (event.Status.DRAFT, event.Status.PUBLISHED):
        return []
    return conflicts(actor, booking, event.starts_at, event.ends_at)


class VenueConflictSerializer(serializers.Serializer):
    code = serializers.ChoiceField(choices=CODES, help_text=(
        "`room_out_of_service` a blocking room outage; `room_outage_warning` a warn-mode outage; "
        "`machine_under_repair` the booked machine is under repair; `space_closed` outside opening "
        "hours or on a closure day. Nothing is changed automatically."))
    severity = serializers.ChoiceField(choices=[BLOCK, WARNING], help_text=(
        "`block` new bookings would be refused for this time; `warning` they would not."))
    starts_at = serializers.DateTimeField(required=False, help_text="Staff with room or service-state authority only.")
    ends_at = serializers.DateTimeField(required=False, help_text="Staff with room or service-state authority only.")
    reason = serializers.CharField(required=False, allow_blank=True,
                                   help_text="The outage reason staff recorded; room or service-state authority only.")

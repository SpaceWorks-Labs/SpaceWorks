"""Decision 242(k) / U4: one staff Schedule, each role seeing only its own layers.

Layers: `bookings`, `events`, `machine_jobs`, `maintenance` (schedules due, work orders due, room outages) and
`shifts` (event volunteer/mentor shifts). A layer exists for the actor only when the action that governs it is
held and its module/capability is on; every queryset goes through rbac (machine rows through the actor's machine
scope, work orders through the maintenance `visible` reach). The Space Manager holds every action, so sees every
layer; the client groups by `area`. Read-only and window-bounded (at most 62 days, 500 entries).
"""

from datetime import date, timedelta

from django.utils import timezone

from apps.accounts import rbac
from apps.makerspaces.local_time import local_day_bounds, to_local
from apps.makerspaces.platform import feature_enabled, module_enabled

A = rbac.Action
MAX_DAYS, MAX_ENTRIES = 62, 500
LAYERS = ("bookings", "events", "machine_jobs", "maintenance", "shifts")


def entry(layer, area, obj_id, title, starts_at, ends_at, status, tab, **filters):
    return {"layer": layer, "area": area, "id": obj_id, "title": title, "starts_at": starts_at, "ends_at": ends_at,
            "status": status, "link": {"tab": tab, "filters": {k: str(v) for k, v in filters.items()}}}


def available_layers(actor, space):
    can = lambda action: rbac.can(actor, action, space.pk)  # noqa: E731
    out = []
    if module_enabled(space, "bookings") and can(A.MANAGE_BOOKINGS):
        out.append("bookings")
    if module_enabled(space, "events") and can(A.MANAGE_EVENTS):
        out += ["events", "shifts"]
    if module_enabled(space, "machines") and can(A.MANAGE_MACHINES):
        out.append("machine_jobs")
    if can(A.MANAGE_MACHINES) or can(A.WORK_REPAIRS) or can(A.RUN_MAINTENANCE) or can(A.MANAGE_BOOKINGS) \
            or can(A.EDIT_INVENTORY):
        out.append("maintenance")
    return [layer for layer in LAYERS if layer in out]


def _bookings(actor, space, low, high):
    from apps.bookings.models import Booking
    rows = rbac.scope_by_action(actor, A.MANAGE_BOOKINGS, Booking.objects.filter(
        space__makerspace=space, status__in=(Booking.Status.PENDING, Booking.Status.CONFIRMED),
        starts_at__lt=high, ends_at__gt=low).select_related("space"), field="space__makerspace_id")
    return [entry("bookings", "bookings", b.pk, b.space.name, b.starts_at, b.ends_at, b.status, "bookings",
                  space=b.space_id, booking=b.pk) for b in rows.order_by("starts_at")]


def _events(actor, space, low, high):
    from apps.events.models import Event
    rows = rbac.scope_by_action(actor, A.MANAGE_EVENTS, Event.objects.filter(
        makerspace=space, status=Event.Status.PUBLISHED, starts_at__lt=high, ends_at__gt=low))
    return [entry("events", "events", e.pk, e.title, e.starts_at, e.ends_at, e.status, "events", event=e.pk)
            for e in rows.order_by("starts_at")]


def _shifts(actor, space, low, high):
    from apps.events.contributions.models_shifts import EventShift
    from apps.events.models import Event
    events = rbac.scope_by_action(actor, A.MANAGE_EVENTS, Event.objects.filter(makerspace=space)).values("pk")
    rows = EventShift.objects.filter(makerspace=space, event__in=events, starts_at__lt=high, ends_at__gt=low)
    return [entry("shifts", "events", s.pk, s.task, s.starts_at, s.ends_at, s.state, "events", event=s.event_id)
            for s in rows.order_by("starts_at")]


def _machine_jobs(actor, space, low, high):
    from apps.machines import role_scope
    from apps.machines.models import MachineServiceRequest
    jobs = role_scope.scoped_service_requests(
        actor, rbac.scope_by_makerspace(actor, MachineServiceRequest.objects.filter(
            makerspace=space, started_at__isnull=False, started_at__lt=high)), [space.pk])
    out = []
    for job in jobs.order_by("started_at")[:MAX_ENTRIES]:
        end = job.completed_at or job.started_at
        if end >= low:
            out.append(entry("machine_jobs", "machines", job.pk, f"Job #{job.pk}", job.started_at, end, job.status,
                             "machines", job=job.pk))
    return out


def _at_noon(space, day):
    return local_day_bounds(space, day)[0]


def _maintenance(actor, space, low, high):
    from apps.maintenance.models import MaintenanceSchedule, RoomOutage
    from apps.maintenance.views_work_orders import visible
    from apps.machines.access_scoping import scope_machines_for_actor
    from apps.machines.models import Machine

    first, last = to_local(space, low).date(), to_local(space, high).date()
    out = []
    if feature_enabled(space, "machines.maintenance") and rbac.can(actor, A.MANAGE_MACHINES, space.pk):
        fleet = scope_machines_for_actor(actor, Machine.objects.filter(makerspace=space))
        for row in MaintenanceSchedule.objects.filter(machine__in=fleet, is_active=True, next_due__gte=first,
                                                      next_due__lte=last).select_related("machine"):
            out.append(entry("maintenance", "machines", row.pk, f"Maintenance: {row.machine.name}",
                             _at_noon(space, row.next_due), _at_noon(space, row.next_due), "due", "machines",
                             machine=row.machine_id))
    for order in visible(actor, space).filter(status__in=("open", "in_progress", "on_hold"), due_on__gte=first,
                                              due_on__lte=last):
        out.append(entry("maintenance", "repairs", order.pk, order.title, _at_noon(space, order.due_on),
                         _at_noon(space, order.due_on), order.status, "repairs"))
    if feature_enabled(space, "bookings.room_maintenance") and rbac.can(actor, A.MANAGE_BOOKINGS, space.pk):
        for outage in RoomOutage.objects.filter(makerspace=space, ended_at__isnull=True, started_at__lt=high).select_related("room"):
            out.append(entry("maintenance", "bookings", outage.pk, f"Outage: {outage.room.name}", outage.started_at,
                             outage.expected_back_at or high, "outage", "bookings", space=outage.room_id))
    return out


BUILDERS = {"bookings": _bookings, "events": _events, "shifts": _shifts, "machine_jobs": _machine_jobs,
            "maintenance": _maintenance}


def parse_window(space, start, end, now=None):
    """`start`/`end` are local calendar dates (ISO); default today through +14 days; at most 62 days."""
    now = now or timezone.now()
    def day(value, default):
        try:
            return date.fromisoformat(value) if value else default
        except ValueError:
            return default
    today = to_local(space, now).date()
    first = day(start, today)
    last = min(max(day(end, first + timedelta(days=14)), first), first + timedelta(days=MAX_DAYS))
    return first, last, local_day_bounds(space, first)[0], local_day_bounds(space, last + timedelta(days=1))[0]


def build_schedule(actor, space, *, start=None, end=None, layers=None, now=None):
    first, last, low, high = parse_window(space, start, end, now)
    allowed = available_layers(actor, space)
    chosen = [layer for layer in allowed if not layers or layer in layers]
    entries = []
    for layer in chosen:
        entries += BUILDERS[layer](actor, space, low, high)
    entries.sort(key=lambda row: (row["starts_at"], row["layer"], row["id"]))
    entries = entries[:MAX_ENTRIES]
    areas = {}
    for row in entries:
        areas[row["area"]] = areas.get(row["area"], 0) + 1
    return {"from": first.isoformat(), "to": last.isoformat(), "layers": allowed, "entries": entries,
            "groups": [{"area": area, "count": count} for area, count in sorted(areas.items())]}


__all__ = ["build_schedule", "available_layers", "LAYERS"]

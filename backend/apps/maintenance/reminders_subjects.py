"""Due and overdue reminders for item and room maintenance (GAP2 M2; L16 follow-up, #128 C-9).

Two reminder sources ride the shared reminder sweeper beside the machine one
(`maintenance.due`): `maintenance.items` (inventory items and units, switch
`inventory.maintenance_reminders`) and `maintenance.rooms` (rooms, switch
`bookings.room_maintenance_reminders`). Each schedule occurrence (its id and next due
date) gets at most one "due soon" notice at the start of the space's local day before it is
due, and one "overdue" notice at the start of the local day after it. Running the schedule
moves the due date on, which makes a new occurrence; the old one is never sent late.

The notice goes to the area's managers through their own family, as L16's issue reports
do: items through `hardware_requests`, rooms through `bookings`. Bodies carry the subject's
name and the due date only. Delivery re-checks the switches, the schedule and the
occurrence at send time, so switching a key off drops what is already queued.
"""

from django.utils.translation import gettext
from datetime import timedelta

from django.db.models import CharField, Q, Value
from django.db.models.functions import Cast, Concat

from apps.accounts import rbac
from apps.hardware_requests.notifications_p2 import fanout, revision, safe_adapter
from apps.integrations.notification_sources import NotificationSource, register_source
from apps.makerspaces.local_time import local_day_bounds, to_local
from apps.makerspaces.platform import feature_enabled
from apps.operations.reminder_consumer_queries import unfinished
from apps.operations.reminder_types import ReminderMessage, ReminderSource, ReminderSubject

KIND = "maintenance.subject_schedule"
LEAD_DAYS = 1
EVENTS = {"due_soon": "maintenance_due_soon", "overdue": "maintenance_overdue"}
ITEMS, ROOMS = "items", "rooms"
AREAS = {
    ITEMS: {"source": "maintenance.items", "module": "staff_admin", "switch": "inventory.maintenance_reminders",
            "subjects": ("inventory_product", "inventory_asset"), "family": ("hardware_requests", "hardware")},
    ROOMS: {"source": "maintenance.rooms", "module": "bookings", "switch": "bookings.room_maintenance_reminders",
            "subjects": ("bookable_space",), "family": ("bookings", "bookings")},
}


def area_of(subject_type):
    return ROOMS if subject_type == "bookable_space" else ITEMS


def label(row):
    subject = row.room if row.subject_type == "bookable_space" else row.asset or row.product
    return getattr(subject, "name", "") or getattr(subject, "asset_tag", "") or str(subject)


def schedules(space, area):
    from .models import SubjectMaintenanceSchedule
    return rbac.scope_for_scheduled_work(SubjectMaintenanceSchedule.objects.select_related(
        "makerspace", "product", "asset", "room"), makerspace_id=space.pk).filter(
        is_active=True, subject_type__in=AREAS[area]["subjects"])


def due_at(space, row, kind):
    day = row.next_due - timedelta(days=LEAD_DAYS) if kind == "due_soon" else row.next_due + timedelta(days=1)
    return local_day_bounds(space, day)[0]


def _discover(space, now, limit, local_tz, *, area):
    today = to_local(space, now).date()
    for kind in ("overdue", "due_soon"):  # drain overdue work first
        rows = unfinished(schedules(space, area), space, AREAS[area]["source"], kind,
                          Concat(Cast("pk", CharField()), Value(":"), Cast("next_due", CharField())))
        window = (Q(next_due__lt=today) if kind == "overdue"
                  else Q(next_due__gte=today, next_due__lte=today + timedelta(days=LEAD_DAYS)))
        for row in rows.filter(window).order_by("next_due", "pk")[:limit]:
            at = due_at(space, row, kind)
            if at <= now:
                yield ReminderSubject(row.reminder_subject, kind, at)


def current(space, reminder, area):
    pk, day = reminder.subject.split(":", 1)
    if not pk.isdigit():
        return None
    return schedules(space, area).filter(pk=int(pk), next_due=day).first()


def _build(space, reminder, now, local_tz, *, area):
    if reminder.kind not in EVENTS or reminder.offset_seconds != 0:
        return None
    row = current(space, reminder, area)
    if row is None or due_at(space, row, reminder.kind) != reminder.due_at:
        return None
    if reminder.kind == "due_soon" and row.next_due < to_local(space, now).date():
        return None
    return ReminderMessage(title=label(row), event=reminder.kind, body=gettext('Maintenance due {value}').format(value=row.next_due.isoformat()))


def _dispatch(space, reminder, message, now, local_tz, *, area):
    row = current(space, reminder, area)
    return notify(row, reminder.kind) if row is not None else None


def version(row, event):
    return revision(row.pk, event, row.next_due, row.is_active)


@safe_adapter
def notify(row, kind):
    area, event = area_of(row.subject_type), EVENTS[kind]
    feature, stream = AREAS[area]["family"]
    name, day = label(row), row.next_due.strftime("%d %b %Y")
    if kind == "due_soon":
        title, text = "Maintenance due soon", f"{row.description} on {name} is due on {day}."
    else:
        title, text = "Maintenance overdue", f"{row.description} on {name} was due on {day} and is overdue."
    return fanout(space=row.makerspace, feature=feature, stream=stream, event=event, kind=KIND, source=row.pk,
                  version=version(row, event), subject=row,
                  staff={"subject": f"{title}: {name}"[:200], "text": text + " Log it in the staff console."},
                  context={"schedule_id": row.pk, "area": area}, staff_context={"schedule_id": row.pk})


def eligible(envelope):
    from django.utils import timezone

    from .models import SubjectMaintenanceSchedule
    kind = next((key for key, value in EVENTS.items() if value == envelope.event), None)
    row = rbac.scope_notification_policy(SubjectMaintenanceSchedule.objects.all(),
                                         makerspace_id=envelope.makerspace_id).filter(pk=envelope.source_id).first()
    if kind is None or row is None or envelope.audience != "staff" or not row.is_active:
        return False
    if version(row, envelope.event) != envelope.revision:
        return False
    space = envelope.makerspace
    if not feature_enabled(space, AREAS[area_of(row.subject_type)]["switch"]):
        return False  # switched off since queueing: the schedule stays, the notice does not
    if due_at(space, row, kind) > timezone.now():
        return False
    return not (kind == "due_soon" and row.next_due < to_local(space, timezone.now()).date())


def register():
    register_source(KIND, NotificationSource(eligible))


def sources():
    from functools import partial
    return tuple(ReminderSource(AREAS[area]["source"], AREAS[area]["module"], partial(_discover, area=area),
                                partial(_build, area=area), AREAS[area]["switch"], partial(_dispatch, area=area))
                 for area in (ITEMS, ROOMS))

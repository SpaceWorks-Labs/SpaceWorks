"""Stage reminders recheck the exact due revision immediately before delivery."""
from django.utils import timezone
from datetime import timedelta
from apps.integrations.notify import NotificationResult
from apps.operations.reminder_types import ReminderSource, ReminderSubject, ReminderMessage
from .response_models import StageFormAssignment
from .notices import enqueue_locked
from .reminder_discovery import undiscovered, stage_prefix, HasUsableOffset
from django.db.models import F
from .trigger_service import participation_live


def identity(row):
    return f"stage-assignment:{row.pk}:due:{row.due_revision}"


def discover(space, now, limit, local_tz):
    rows = StageFormAssignment.objects.filter(event__makerspace=space, state="open", imported_paused=False,
        event__status__in=("published", "completed"), opens_at__lte=now, effective_due_at__gt=now).select_related("stage_form")
    rows = undiscovered(rows, space=space, source="stage_forms", prefix=stage_prefix(), due_field="effective_due_at", exact=True)
    rows = rows.annotate(_has_offset=HasUsableOffset(F("stage_form__reminder_offsets"), F("effective_due_at"), F("triggered_at"))).filter(
        _has_offset=True).order_by("effective_due_at", "pk")
    for row in rows[:min(limit, 100)]:
        offsets = tuple(value for value in row.stage_form.reminder_offsets
            if row.effective_due_at + timedelta(seconds=value) > row.triggered_at)
        if offsets:
            yield ReminderSubject(identity(row), "due", row.effective_due_at, offsets)


def resolve(space, schedule, now):
    parts = schedule.subject.split(":")
    if len(parts) != 4 or parts[0] != "stage-assignment" or parts[2] != "due" or not parts[1].isdecimal():
        return None
    row = StageFormAssignment.objects.select_related("event__makerspace", "stage_form").filter(
        pk=int(parts[1]), event__makerspace=space, state="open", imported_paused=False).first()
    if row is None or identity(row) != schedule.subject or row.effective_due_at != schedule.due_at or now >= row.effective_due_at:
        return None
    return row if row.event.status != "cancelled" and participation_live(row) and row.opens_at <= now and schedule.offset_seconds in row.stage_form.reminder_offsets else None


def build(space, schedule, now, local_tz):
    return ReminderMessage("Your event form is due", "stage_form.reminder") if resolve(space, schedule, now) else None


def dispatch(space, schedule, message, now, local_tz):
    row = resolve(space, schedule, timezone.now())
    if row is None:
        return NotificationResult(False)
    result = enqueue_locked(row, "reminder", identity=str(schedule.pk))
    return NotificationResult(bool(result), {"envelope": 1} if result else {})


STAGE_REMINDER_SOURCE = ReminderSource("stage_forms", "events", discover, build, dispatch=dispatch)

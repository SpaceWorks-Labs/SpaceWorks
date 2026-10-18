"""RSVP deadlines have their own canonical identity, even with no stage forms."""
from datetime import timezone as utc
from django.utils import timezone
from apps.events.hackathons.admission_models import HackathonApplication
from apps.integrations.notification_sources import NotificationSource
from apps.integrations.notification_outbox import emit
from apps.integrations.notify import NotificationResult
from apps.operations.reminder_types import ReminderSource, ReminderSubject, ReminderMessage
from apps.makerspaces.platform import module_enabled
from apps.makerspaces.servability import is_servable
from apps.notifications.inbox import eligible_owner


def identity(row):
    # ISO encoding deliberately retains +00:00, including fractional seconds.
    # All equivalent offsets map to one identity. G1's literal fixture remains
    # required before this adapter can be enabled by the integrator.
    due = row.rsvp_due_at.astimezone(utc.utc).isoformat()
    return f"application:{row.pk}:offer:{row.decision_revision}:due:{due}"


def discover(space, now, limit, local_tz):
    rows = HackathonApplication.objects.filter(event__makerspace=space, state="offered",
        rsvp_due_at__gt=now).order_by("rsvp_due_at", "pk")
    for row in rows[:min(limit, 100)]:
        yield ReminderSubject(identity(row), "rsvp", row.rsvp_due_at, (-86400,))


def resolve(space, schedule, now):
    parts = schedule.subject.split(":", 2)
    if len(parts) != 3 or parts[0] != "application" or not parts[1].isdecimal():
        return None
    row = HackathonApplication.objects.select_related("event__makerspace", "member").filter(
        pk=int(parts[1]), event__makerspace=space, state="offered", rsvp_due_at__gt=now).first()
    return row if row and identity(row) == schedule.subject and row.rsvp_due_at == schedule.due_at else None


def build(space, schedule, now, local_tz):
    return ReminderMessage("Your event RSVP is due", "rsvp_reminder") if resolve(space, schedule, now) else None


def dispatch(space, schedule, message, now, local_tz):
    row = resolve(space, schedule, timezone.now())
    if row is None or not eligible_owner(space, row.member_id):
        return NotificationResult(False)
    emit(makerspace=space, recipient=row.member, feature="events", stream="events", event="rsvp_reminder",
        audience="member", dedup_key=f"event-rsvp:{schedule.pk}", source_kind="events.rsvp_deadline",
        source_id=str(row.pk), revision=str(row.decision_revision), subject=row,
        context={"rsvp_due_at": row.rsvp_due_at.astimezone(utc.utc).isoformat()},
        rendered={"subject": "Your event RSVP is due", "text": "Sign in to respond to your current offer.",
                  "link": f"/member/events/{row.event_id}"})
    return NotificationResult(True, {"envelope": 1})


def eligible(envelope):
    row = HackathonApplication.objects.select_related("event__makerspace").filter(pk=envelope.source_id,
        event__makerspace_id=envelope.makerspace_id, member_id=envelope.recipient_id, state="offered").first()
    return bool(row and row.rsvp_due_at and timezone.now() < row.rsvp_due_at
        and is_servable(row.event.makerspace) and module_enabled(row.event.makerspace, "events")
        and eligible_owner(row.event.makerspace, row.member_id)
        and row.rsvp_due_at.astimezone(utc.utc).isoformat() == envelope.context.get("rsvp_due_at")
        and str(row.decision_revision) == envelope.revision)


RSVP_REMINDER_SOURCE = ReminderSource("events.rsvp_deadline", "events", discover, build, dispatch=dispatch)
RSVP_NOTICE_SOURCE = NotificationSource(eligible)

"""E3 registration reminders on the shared F1 schedule and notification matrix."""

from datetime import timedelta

from django.db.models import Q
from django.utils import timezone

from apps.integrations.notification_links import local_link
from apps.accounts import rbac
from apps.integrations.notify import NotificationResult
from apps.events.models import Event, EventRegistration
from apps.integrations.email_templates_fablab import events_context
from apps.makerspaces.reminder_policy import reminder_offsets
from apps.makerspaces.platform import module_enabled
from apps.integrations.email_templates import render
from apps.integrations.notification_outbox import emit
from apps.hardware_requests.notification_projection import addressed_context
from apps.operations.reminder_members import occurrence_subject, unfinished_subjects
from apps.operations.reminder_types import ReminderMessage, ReminderSource, ReminderSubject

SOURCE_KEY = "events.registration"


def _registrations(makerspace):
    # Durable registration provenance, rather than today's collaboration, chooses
    # the member's tenant. Legacy rows without provenance belong to the venue.
    rows = rbac.scope_for_scheduled_work(
        EventRegistration.objects.all(), field="event__makerspace_id",
    ).filter(
        Q(registered_via_makerspace=makerspace)
        | Q(registered_via_makerspace__isnull=True, event__makerspace=makerspace),
        status=EventRegistration.Status.REGISTERED, event__status=Event.Status.PUBLISHED,
        member__isnull=False,
    )
    return rows.select_related("event__makerspace")


def discover_event_reminders(makerspace, now, limit, local_tz):
    # No membership-module gate: an account-only attendee owns their registration and is
    # reminded through their own channels (eligible_owner still refuses a revoked member).
    offsets = reminder_offsets(makerspace, "event")
    if not offsets:
        return
    rows = unfinished_subjects(_registrations(makerspace), makerspace, SOURCE_KEY, offsets,
                              now=now, due_field="event__starts_at")
    rows = rows.filter(event__starts_at__gt=now,
                       event__starts_at__lte=now + timedelta(seconds=-min(offsets)))
    for row in rows.order_by("event__starts_at", "pk")[:limit]:
        yield ReminderSubject(occurrence_subject(row.pk, row.event.starts_at), "starts",
                              row.event.starts_at, offsets)


def _eligible(makerspace, schedule, now):
    if schedule.kind != "starts" or schedule.offset_seconds not in reminder_offsets(makerspace, "event"):
        return None
    subject_id = schedule.subject.split(":", 1)[0]
    if not subject_id.isdecimal():
        return None
    row = _registrations(makerspace).filter(pk=int(subject_id)).first()
    if (row is None or row.event.starts_at != schedule.due_at or row.event.starts_at <= now
            or not module_enabled(row.event.makerspace, "events")
            or _recipient(makerspace, row.member_id) is None):
        return None
    return row


def _recipient(makerspace, member_id):
    from apps.accounts.models import User
    from .notification_envelopes import _owner_allowed
    from apps.integrations.recipients_owners import eligible_owner
    if not member_id or not eligible_owner(makerspace, member_id):
        return None
    if not _owner_allowed(makerspace, "reminder"):
        return None
    return User.objects.filter(pk=member_id).first()


def build_event_reminder(makerspace, schedule, now, local_tz):
    row = _eligible(makerspace, schedule, now)
    if row is None:
        return None
    return ReminderMessage(title=row.event.title, event="events.reminder")


def dispatch_event_reminder(makerspace, schedule, message, now, local_tz):
    # Re-read immediately before delivery; cancellation can happen after discovery.
    row = _eligible(makerspace, schedule, timezone.now())
    if row is None:
        return NotificationResult(False)
    member = _recipient(makerspace, row.member_id)
    if member is None:
        return NotificationResult(False)
    with timezone.override(makerspace.timezone):
        context = events_context(row.event, "reminder", row, next_steps="Your event is coming up.")
        template = render(makerspace, "events", "requester", "reminder", context)
    # Owner-only and personal: selected channels, never staff rooms. The schedule row is the
    # durable dedup identity, so a retried sweep cannot remind twice.
    emit(makerspace=makerspace, recipient=member, feature="events", stream="events", event="reminder",
         audience="requester", dedup_key=f"ev:reminder:{schedule.pk}", source_kind="events.reminder",
         source_id=str(row.pk), revision=schedule.subject[:64], subject=row,
         context={**addressed_context(makerspace, "events", "reminder", "requester", context),
                  "event_id": row.event_id, "registration_id": row.pk,
                  "starts_at": row.event.starts_at.isoformat(), "offset_seconds": schedule.offset_seconds},
         rendered={"subject": template["subject"], "text": template["text_body"],
                   "html": template.get("html_body", ""),
                   "link": local_link(makerspace, "member", f"events/{row.pk}/ticket")})
    return NotificationResult(True, {"envelope": 1})


EVENT_REMINDER_SOURCE = ReminderSource(
    key=SOURCE_KEY, module="events", discover=discover_event_reminders,
    build=build_event_reminder, dispatch=dispatch_event_reminder,
)

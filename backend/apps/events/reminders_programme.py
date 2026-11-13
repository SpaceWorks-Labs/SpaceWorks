"""Recover C's persisted due notices through the existing tenant reminder scheduler."""
from django.utils.translation import gettext
from functools import partial

from apps.integrations.notify import NotificationResult
from apps.operations.reminder_types import ReminderMessage, ReminderSource, ReminderSubject


def _rows(makerspace, kind):
    if kind == "help":
        from .mentoring.models_rounds import MentorNotificationIntent
        return MentorNotificationIntent.objects.filter(makerspace=makerspace,
            delivered_at__isnull=True, attempts__lt=15, request__practice_run_id__isnull=True)
    from .contributions.models_notices import EventContributorNotice
    rows = EventContributorNotice.objects.filter(makerspace=makerspace, delivered_at__isnull=True, attempts__lt=15)
    return rows.filter(signup__isnull=False) if kind == "shift" else rows.filter(booking__isnull=False)


def discover(makerspace, now, limit, local_tz, *, kind):
    for row in _rows(makerspace, kind).filter(available_at__lte=now).order_by("available_at", "pk")[:limit]:
        yield ReminderSubject(subject=f"{row.pk}:{row.generation}", kind=kind, due_at=row.available_at)


def _notice(makerspace, schedule, kind):
    try:
        pk, generation = map(int, schedule.subject.split(":"))
    except (TypeError, ValueError, AttributeError):
        return None
    return _rows(makerspace, kind).filter(pk=pk, generation=generation).first()


def build(makerspace, schedule, now, local_tz, *, kind):
    if _notice(makerspace, schedule, kind) is None:
        return None
    # Domain adapters select recipients and render the actual personal message.
    return ReminderMessage(title=gettext("Event programme update"), event="programme_notice")


def dispatch(makerspace, schedule, message, now, local_tz, *, kind):
    row = _notice(makerspace, schedule, kind)
    if row is None:
        return NotificationResult(False)
    if kind == "help":
        from .mentoring.notifications import deliver_one
    else:
        from .contributions.notifications import deliver_one
    delivered = deliver_one(row.pk)
    # A competing worker's live lease is retried; the owning notice remains the
    # deduplication authority, including after a lost scheduler response.
    row.refresh_from_db()
    if delivered or row.delivered_at:
        return NotificationResult(True)
    return NotificationResult(False, failed_counts={"programme": 1})


PROGRAMME_REMINDER_SOURCES = tuple(
    ReminderSource(key, "events", partial(discover, kind=kind), partial(build, kind=kind),
        feature, partial(dispatch, kind=kind), requires_notifications=False)
    for key, kind, feature in (
        ("events.volunteer_shift", "shift", "events.volunteering"),
        ("events.office_hours", "booking", "events.mentoring"),
        ("events.mentor_help", "help", "events.mentoring"),
    )
)

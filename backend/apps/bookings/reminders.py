"""Booking reminders for eligible account owners, with durable occurrence sources."""

from datetime import timedelta

from django.db.models import CharField, OuterRef, Q, Value
from django.db.models.functions import Cast, Concat
from django.utils import timezone

from apps.accounts import rbac
from apps.integrations.notify import NotificationResult
from apps.makerspaces.reminder_policy import reminder_offsets
from apps.operations.models import ReminderSchedule
from apps.operations.reminder_members import occurrence_subject, unfinished_subjects
from apps.operations.reminder_services import _reminder_write
from apps.operations.reminder_types import ReminderMessage, ReminderSource, ReminderSubject
from .communication_recipients import notification_account
from .models import Booking
from .notifications import _effective_toggle
from .reminder_delivery import SOURCE_KEY, identity


def _bookings(makerspace):
    return rbac.scope_for_scheduled_work(
        Booking.objects.all(), makerspace_id=makerspace.pk, field="space__makerspace_id",
    ).filter(status=Booking.Status.CONFIRMED, member__isnull=False).select_related("space__makerspace")


def discover_booking_reminders(makerspace, now, limit, local_tz):
    offsets = reminder_offsets(makerspace, "booking")
    if not offsets:
        return
    prefix = Concat(Cast("pk", CharField()), Value(":"), Cast("calendar_sequence", CharField()))
    # Legacy subjects have a UTC date after the booking ID, not a revision.
    # Approval already incremented calendar_sequence before this upgrade.
    legacy = Q(subject__regex=Concat(Value("^"), Cast(OuterRef("pk"), CharField()), Value(r":[0-9]{4}-")))
    rows = unfinished_subjects(_bookings(makerspace), makerspace, SOURCE_KEY, offsets,
                               now=now, identity=prefix, legacy_subject_filter=legacy)
    rows = rows.filter(starts_at__gt=now, starts_at__lte=now + timedelta(seconds=-min(offsets)))
    for row in rows.order_by("starts_at", "pk")[:limit]:
        _upgrade_pending_legacy(makerspace, row)
        yield ReminderSubject(identity(row), "starts", row.starts_at, offsets)


def _upgrade_pending_legacy(makerspace, row, *, schedule_id=None):
    # Replace only unclaimed steps, atomically with creating their new identity.
    # A worker claiming first keeps its legacy duplicate/uncertain-send fence.
    with _reminder_write(makerspace.pk):
        schedules = rbac.scope_for_scheduled_work(
            ReminderSchedule.objects.all(), makerspace_id=makerspace.pk,
        )
        pending = schedules.select_for_update().filter(
            source=SOURCE_KEY, subject=occurrence_subject(row.pk, row.starts_at),
            kind="starts", due_at=row.starts_at, state=ReminderSchedule.State.PENDING,
        ).order_by("pk")
        if schedule_id is not None:
            pending = pending.filter(pk=schedule_id)
        upgraded = []
        for old in pending:
            # An already-seeded replacement (including a committed claim) wins.
            current, _ = schedules.get_or_create(
                makerspace=makerspace, source=SOURCE_KEY, subject=identity(row),
                kind=old.kind, offset_seconds=old.offset_seconds,
                defaults={"due_at": old.due_at, "remind_at": old.remind_at},
            )
            schedules.filter(pk=old.pk, state=ReminderSchedule.State.PENDING).delete()
            upgraded.append(current)
        return upgraded


def normalize_booking_claim(makerspace, schedule):
    subject_id = schedule.subject.split(":", 1)[0]
    if not subject_id.isdecimal():
        return schedule
    row = _bookings(makerspace).filter(pk=int(subject_id)).first()
    if row is None or schedule.subject != occurrence_subject(row.pk, row.starts_at):
        return schedule
    # Discovery and claims have different orderings and batch boundaries. Only
    # upgrade this locked candidate, avoiding locks on another worker's batch.
    upgraded = _upgrade_pending_legacy(makerspace, row, schedule_id=schedule.pk)
    return upgraded[0] if upgraded else schedule


def _eligible(makerspace, schedule, now):
    if schedule.kind != "starts" or schedule.offset_seconds not in reminder_offsets(makerspace, "booking"):
        return None
    subject_id = schedule.subject.split(":", 1)[0]
    if not subject_id.isdecimal():
        return None
    row = _bookings(makerspace).filter(pk=int(subject_id)).first()
    if (row is None or identity(row) != schedule.subject or row.starts_at != schedule.due_at
            or row.starts_at <= now or not _effective_toggle(row)
            or notification_account(row.space.makerspace, row.member_id, "reminder") is None):
        return None
    # Discovery seeds all offsets. A later step must not redispatch an earlier
    # legacy step whose completed/uncertain claim uses the pre-upgrade subject.
    if rbac.scope_for_scheduled_work(
        ReminderSchedule.objects.all(), makerspace_id=makerspace.pk,
    ).filter(
        source=SOURCE_KEY, subject=occurrence_subject(row.pk, row.starts_at),
        kind=schedule.kind, due_at=row.starts_at, offset_seconds=schedule.offset_seconds,
    ).exclude(state=ReminderSchedule.State.PENDING).exists():
        return None
    return row


def build_booking_reminder(makerspace, schedule, now, local_tz):
    row = _eligible(makerspace, schedule, now)
    return ReminderMessage(title=row.space.name, event="bookings.reminder") if row else None


def dispatch_booking_reminder(makerspace, schedule, message, now, local_tz):
    row = _eligible(makerspace, schedule, timezone.now())
    if row is None:
        return NotificationResult(False)
    account = notification_account(row.space.makerspace, row.member_id, "reminder")
    if account is None:
        return NotificationResult(False)
    from .reminder_envelopes import emit_reminder
    # One personal envelope per reminder step; the owner's chosen channels deliver it and
    # `notification_sources.reminder_eligible` re-checks the booking at every attempt.
    if emit_reminder(row, schedule, account):
        return NotificationResult(True, {"envelope": 1})
    return NotificationResult(False, {}, {"envelope": 1})


BOOKING_REMINDER_SOURCE = ReminderSource(
    key=SOURCE_KEY, module="bookings", discover=discover_booking_reminders,
    build=build_booking_reminder, dispatch=dispatch_booking_reminder,
    normalize_claim=normalize_booking_claim,
)

"""Attendance confirmation, "Are you still coming?" (X43, #128 C-35).

Staff send it from the Emails tab; nothing sends it automatically. A send (or reminder)
is refused within 12 hours of the previous one. The emails go out from a bounded Celery
task. Each registered person answers on their own private page, with an optional note.

With the event's "free the place on No" switch on (off by default), a No:
- on a free place cancels the registration, which releases the seat and promotes the waitlist;
- on a paid place cancels under the refund policy, which opens a refund DUE case for staff
  to decide -- money never moves automatically (#59, #60);
- on a seat from a multi-ticket order changes nothing: those are left to staff.
"""
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from apps.audit import services as audit
from apps.makerspaces.platform import feature_enabled

from .hackathons.admission_errors import fail
from .models import EventRegistration
from .models_participation import EventAttendanceReply, EventAttendanceRound, EventParticipationSettings
from .services_write_boundary import event_write

FEATURE = "events.attendance_confirmation"
INTERVAL = timedelta(hours=12)


def require_feature(event):
    if not feature_enabled(event.makerspace, FEATURE):
        fail("not_found", "Not found.", status=404)


def _targets(event):
    return EventRegistration.objects.filter(event=event, status=EventRegistration.Status.REGISTERED,
                                            member__isnull=False, is_crew=False)


@event_write(permission="manage_registrations")
def send(event, *, actor, kind):
    require_feature(event)
    now = timezone.now()
    if event.status != event.Status.PUBLISHED or now >= event.ends_at:
        fail("event_closed", "Attendance can only be confirmed for an upcoming published event.")
    last = EventAttendanceRound.objects.filter(event=event).order_by("-created_at").first()
    if last and now - last.created_at < INTERVAL:
        wait = int((last.created_at + INTERVAL - now).total_seconds())
        fail("attendance_too_soon", "Wait 12 hours between attendance emails.", status=429,
             fields={"retry_after_seconds": [str(wait)]})
    if kind == EventAttendanceRound.Kind.REMINDER and not EventAttendanceReply.objects.filter(event=event).exists():
        fail("attendance_not_asked", "Send the confirmation before a reminder.", status=400)
    if kind == EventAttendanceRound.Kind.CONFIRMATION:
        asked = EventAttendanceReply.objects.filter(event=event).values("registration_id")
        for registration in _targets(event).exclude(pk__in=asked):
            EventAttendanceReply.objects.create(makerspace=event.makerspace, event=event, registration=registration,
                                                asked_at=now)
    pending = EventAttendanceReply.objects.filter(event=event, answer="", registration__in=_targets(event))
    round_ = EventAttendanceRound.objects.create(makerspace=event.makerspace, event=event, kind=kind,
                                                 recipients=pending.count(), sent_by=actor)
    audit.record(actor, "event.attendance.sent", makerspace=event.makerspace, target=event,
                 meta={"event_id": event.pk, "round_id": round_.pk, "kind": kind, "recipients": round_.recipients})
    from .tasks_attendance import send_attendance_round_task
    transaction.on_commit(lambda: send_attendance_round_task.delay(round_.pk), robust=True)
    return round_


def deliver_round(round_id, *, limit=2000):
    """The task body: one notice per unanswered, still-registered person, at most `limit`."""
    from .notices_r2_l21a import attendance_notice
    round_ = EventAttendanceRound.objects.select_related("event__makerspace").filter(pk=round_id).first()
    if round_ is None or round_.state == EventAttendanceRound.State.SENT:
        return 0
    name = "attendance_reminder" if round_.kind == EventAttendanceRound.Kind.REMINDER else "attendance_confirmation"
    replies = (EventAttendanceReply.objects.filter(event=round_.event, answer="", registration__in=_targets(round_.event))
               .select_related("event__makerspace", "registration").order_by("pk")[:limit])
    sent = 0
    for reply in replies:
        if attendance_notice(reply, name, revision=f"r{round_.pk}") is not None:
            sent += 1
    EventAttendanceRound.objects.filter(pk=round_.pk).update(sent=sent, state=EventAttendanceRound.State.SENT,
                                                             finished_at=timezone.now())
    EventAttendanceReply.objects.filter(pk__in=[r.pk for r in replies]).update(reminded_at=timezone.now())
    return sent


def _paid(registration):
    from apps.payments.models import Payment
    settled = (Payment.Status.PAID_ONLINE, Payment.Status.PAID_OFFLINE)
    if Payment.objects.filter(subject_type=Payment.SubjectType.EVENT_REGISTRATION, subject_id=registration.pk,
                              status__in=settled).exists():
        return True
    seat = getattr(registration, "order_seat", None)
    return bool(seat and seat.order.status == "paid" and seat.order.total > 0)


def _multi_ticket_order(registration):
    seat = getattr(registration, "order_seat", None)
    return bool(seat and seat.order.seats.exclude(status="void").count() > 1)


@event_write
def reply(registration, *, actor, answer, note=""):
    from .services_registration_state import cancel_registration
    event = registration.event
    require_feature(event)
    row = EventAttendanceReply.objects.select_for_update().filter(registration=registration).first()
    if row is None or registration.member_id != actor.pk:
        fail("not_found", "Not found.", status=404)
    if timezone.now() >= event.ends_at:
        fail("event_closed", "This event has ended.")
    if row.effect != EventAttendanceReply.Effect.NONE:
        fail("attendance_final", "Your place was already released.")
    row.answer, row.note, row.replied_at = answer, note[:1000], timezone.now()
    if answer == EventAttendanceReply.Answer.NO and EventParticipationSettings.for_event(event).attendance_free_on_no:
        locked = EventRegistration.objects.get(pk=registration.pk)
        if locked.status == EventRegistration.Status.REGISTERED:
            if _multi_ticket_order(locked):
                row.effect = EventAttendanceReply.Effect.LEFT_TO_STAFF
            else:
                paid = _paid(locked)
                cancel_registration(locked, actor=None)
                row.effect = EventAttendanceReply.Effect.DUE_CASE if paid else EventAttendanceReply.Effect.RELEASED
    row.save()
    audit.record(actor, "event.attendance.replied", makerspace=event.makerspace, target=registration,
                 meta={"event_id": event.pk, "registration_id": registration.pk, "answer": answer, "effect": row.effect})
    if answer == EventAttendanceReply.Answer.NO:
        from .notices_r2_l21a import reply_notice
        reply_notice(row)
    return row

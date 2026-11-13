"""Loan ladder source for F1. No addresses or payloads persist in schedule rows."""

from django.utils.translation import gettext
from datetime import timedelta

from itertools import islice

from apps.accounts import rbac
from apps.hardware_requests.models import HardwareRequest
from apps.hardware_requests.renewal_workflow import ACTIVE_LOAN_STATUSES
from apps.makerspaces.models_loan_policy import MakerspaceLoanPolicy
from apps.operations.models_reminders import ReminderSchedule
from apps.operations.reminder_types import ReminderMessage, ReminderSource, ReminderSubject


def _rows(model, makerspace):
    return rbac.scope_for_scheduled_work(model.objects.all(), makerspace_id=makerspace.pk)


def _subject(loan):
    # A new due date is a new occurrence. Old claims never become retryable.
    return f"{loan.pk}:{loan.return_due_at.isoformat()}"


def _offsets(policy, kind):
    if kind == "escalation":
        return (policy.loan_escalate_overdue_days * 86400,) if policy.loan_escalate_overdue_days else ()
    return tuple(hour * 3600 for hour in policy.loan_reminder_offsets_hours)


def _discover(makerspace, now, limit, local_tz, *, kind, source):
    policy = _rows(MakerspaceLoanPolicy, makerspace).first()
    if policy is None:
        return
    offsets = _offsets(policy, kind)
    if not offsets:
        return
    rows = _rows(HardwareRequest, makerspace).filter(
        status__in=ACTIVE_LOAN_STATUSES, return_due_at__isnull=False,
        return_due_at__lte=now - timedelta(seconds=min(offsets)),
    ).order_by("return_due_at", "pk")
    count = 0
    # Fetch claim tombstones by page, rather than one query per old loan.
    # Completed older subjects must not crowd out later eligible borrowers.
    iterator = rows.iterator(chunk_size=200)
    while page := list(islice(iterator, 200)):
        from apps.operations.cloud_jobs import bounded
        bounded.check()
        completed = {}
        for subject, offset in _rows(ReminderSchedule, makerspace).filter(
            source=source, subject__in=[_subject(loan) for loan in page], kind=kind,
        ).exclude(state=ReminderSchedule.State.PENDING).values_list("subject", "offset_seconds"):
            completed.setdefault(subject, set()).add(offset)
        for loan in page:
            subject = _subject(loan)
            eligible = tuple(offset for offset in offsets
                             if offset not in completed.get(subject, ())
                             and loan.return_due_at + timedelta(seconds=offset) <= now)
            # A legacy overdue reminder proves the zero-offset delivery already ran.
            if kind == "borrower" and loan.return_reminder_sent_at:
                eligible = tuple(offset for offset in eligible if offset != 0)
            if eligible:
                yield ReminderSubject(subject, kind, loan.return_due_at, eligible)
                count += 1
                if count >= limit:
                    return


def discover_borrower(makerspace, now, limit, local_tz):
    return _discover(makerspace, now, limit, local_tz, kind="borrower", source="loans.return")


def discover_escalation(makerspace, now, limit, local_tz):
    return _discover(makerspace, now, limit, local_tz, kind="escalation", source="loans.escalation")


def _current(makerspace, reminder):
    policy = _rows(MakerspaceLoanPolicy, makerspace).first()
    if policy is None or reminder.offset_seconds not in _offsets(policy, reminder.kind):
        return None
    request_id = reminder.subject.partition(":")[0]
    loan = _rows(HardwareRequest, makerspace).select_related("requester").filter(
        pk=request_id, status__in=ACTIVE_LOAN_STATUSES, return_due_at=reminder.due_at,
    ).first()
    if loan is None or _subject(loan) != reminder.subject:
        return None
    if reminder.kind == "borrower" and reminder.offset_seconds == 0 and loan.return_reminder_sent_at:
        return None
    return loan


def build_reminder(makerspace, reminder, now, local_tz):
    loan = _current(makerspace, reminder)
    if loan is None:
        return None
    due = loan.return_due_at.astimezone(local_tz).strftime("%Y-%m-%d %H:%M %Z (%z)")
    overdue = now > loan.return_due_at
    title = "Overdue loan escalation" if reminder.kind == "escalation" else "Loan return reminder"
    return ReminderMessage(
        title=title, event="loan.overdue_escalated" if reminder.kind == "escalation" else "loan.return_reminder",
        body=gettext('Request #{pk} {value}; return by {due}.').format(pk=loan.pk, value='is overdue' if overdue else 'is due for return', due=due),
        level="warning" if overdue else "info",
    )


def dispatch_reminder(makerspace, reminder, message, now, local_tz):
    from apps.hardware_requests.loan_reminder_notifications import deliver_loan_reminder

    # Revalidate after the shared source gate too, just before outbound delivery.
    loan = _current(makerspace, reminder)
    if loan is None:
        return
    result = deliver_loan_reminder(makerspace, loan, reminder, message, local_tz)
    # Escalations already reserve staff-only envelopes. A legacy feed mirror
    # would create a second staff alert outside that source-backed identity.
    if reminder.kind == "borrower" and reminder.offset_seconds == 0 and result and result.scheduled:
        _rows(HardwareRequest, makerspace).filter(pk=loan.pk, return_due_at=reminder.due_at).update(
            return_reminder_sent_at=now,
        )
    if result is None or result.failed_counts:
        # The claim remains permanent even when delivery fails. Preserve that
        # at-most-once rule, but expose the failure to F1 instead of recording success.
        # None means the adapter itself failed (its savepoint rolled back); nobody
        # reachable is NOT a failure, exactly as before.
        raise RuntimeError("Loan reminder delivery failed.")


LOAN_REMINDER_SOURCES = (
    ReminderSource("loans.return", "request_workflow", discover_borrower, build_reminder,
                   dispatch=dispatch_reminder, requires_notifications=False),
    ReminderSource("loans.escalation", "request_workflow", discover_escalation, build_reminder,
                   dispatch=dispatch_reminder),
)

"""Core payee-collection reminders use the shared five-minute reminder sweep."""
from datetime import timedelta
from uuid import UUID
from django.db.models import Exists, OuterRef
from apps.integrations.notify import NotificationResult
from apps.makerspaces.servability import is_servable
from apps.notifications.inbox import eligible_owner
from apps.operations.models_reminders import ReminderSchedule
from apps.operations.reminder_types import ReminderSource, ReminderSubject, ReminderMessage
from .obligation_models import EventPayoutObligation
from .notices import enqueue_locked

SOURCE_KEY = "finance.event_payout_details"
OFFSETS = (86400, 7 * 86400)


def identity(row):
    return f"obligation:{row.pk}:version:{row.version}"


def needs_details(row):
    from .eligibility_workflow import active_holds
    from .payee_workflow import current
    from .queries import paid
    if (row.state != "open" or row.hold_reason_code or row.eligibility_status == "held"
            or active_holds(row).exists() or not eligible_owner(row.makerspace, row.owner_member_id)
            or not is_servable(row.makerspace) or paid(row) >= row.approved_minor):
        return False
    payee = current(row)
    if payee is None or payee.state == "purged":
        return True
    latest = payee.reviews.order_by("-sequence").first()
    return latest is not None and latest.kind == "correction_requested"


def discover(space, now, limit, local_tz):
    if not is_servable(space):
        return
    # Exclude already scheduled identities BEFORE the limit, so the first page
    # cannot starve later unpaid owners. Each step has its own durable claim.
    from django.db.models import CharField, Value
    from django.db.models.functions import Cast, Concat
    from .payee_models import EventPayeeRevision
    from .eligibility_models import PayoutHold
    current = EventPayeeRevision.objects.filter(obligation_id=OuterRef("pk"), state="current")
    waiting = current.exclude(reviews__kind="correction_requested")
    holds = PayoutHold.objects.filter(obligation_id=OuterRef("pk"), action="hold", released_by_entry__isnull=True)
    rows = EventPayoutObligation.objects.filter(makerspace=space, state="open", hold_reason_code="",
        owner_member__is_active=True, owner_member__access_status="active").exclude(eligibility_status="held").annotate(
        has_waiting_payee=Exists(waiting), has_hold=Exists(holds),
        reminder_subject=Concat(Value("obligation:"), Cast("pk", CharField()), Value(":version:"), Cast("version", CharField()))
    ).filter(has_waiting_payee=False, has_hold=False)
    for offset in OFFSETS:
        finished = ReminderSchedule.objects.filter(makerspace=space, source=SOURCE_KEY,
            subject=OuterRef("reminder_subject"), kind=f"details:{offset}")
        candidates = rows.annotate(done=Exists(finished)).filter(done=False, created_at__lte=now - timedelta(seconds=offset))
        for row in candidates.select_related("makerspace").order_by("created_at", "pk")[:min(limit, 100)]:
            if needs_details(row):
                yield ReminderSubject(identity(row), f"details:{offset}", row.created_at, (offset,))


def resolve(space, schedule):
    parts = schedule.subject.split(":")
    if len(parts) != 4 or parts[0] != "obligation" or parts[2] != "version":
        return None
    try:
        identifier = UUID(parts[1])
    except ValueError:
        return None
    row = EventPayoutObligation.objects.select_related("makerspace").filter(pk=identifier, makerspace=space).first()
    if row is None or identity(row) != schedule.subject or row.created_at != schedule.due_at:
        return None
    return row if (schedule.offset_seconds in OFFSETS and schedule.kind == f"details:{schedule.offset_seconds}"
                   and needs_details(row)) else None


def build(space, schedule, now, local_tz):
    return ReminderMessage("Reimbursement details needed", "event_payout.details_reminder") if resolve(space, schedule) else None


def dispatch(space, schedule, message, now, local_tz):
    from .worker_boundary import locked_obligation
    row = resolve(space, schedule)
    if row is None:
        return NotificationResult(False)
    with locked_obligation(row.pk) as row:
        if identity(row) != schedule.subject or not needs_details(row):
            return NotificationResult(False)
        envelope = enqueue_locked(row, "details_reminder", identity=str(schedule.pk))
        return NotificationResult(bool(envelope), {"envelope": int(envelope is not None)})


PAYOUT_DETAILS_SOURCE = ReminderSource(SOURCE_KEY, "events", discover, build, dispatch=dispatch)

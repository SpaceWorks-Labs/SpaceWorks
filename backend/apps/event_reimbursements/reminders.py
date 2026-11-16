"""Existing reminder sweep supplies deduplication and bounded due-time discovery."""
from django.utils import timezone
from apps.integrations.notify import NotificationResult
from apps.operations.reminder_types import ReminderSource, ReminderSubject, ReminderMessage
from .award_models import GrantAward
from .claim_models import ReimbursementClaim
from .notices import enqueue_locked
from .decision_summary import utc


def undiscovered(rows, *, space, award):
    from django.db.models import Exists, OuterRef, Value, CharField
    from django.db.models.functions import Cast, Concat
    from apps.operations.models_reminders import ReminderSchedule
    prefix = Concat(Value("award:" if award else "claim:"), Cast(OuterRef("pk"), CharField()),
        Value(":offer:" if award else ":due:"), Cast(OuterRef("due_revision"), CharField()),
        Value(":due:" if award else ""))
    scheduled = ReminderSchedule.objects.filter(makerspace=space,
        source="event_reimbursements.award_accept" if award else "event_reimbursements.claim_due")
    scheduled = scheduled.filter(subject__startswith=prefix) if award else scheduled.filter(subject=prefix)
    return rows.annotate(already_scheduled=Exists(scheduled)).filter(already_scheduled=False)


def award_identity(row):
    return f"award:{row.pk}:offer:{row.due_revision}:due:{utc(row.accept_by)}"


def claim_identity(row):
    return f"claim:{row.pk}:due:{row.due_revision}"


def discover_awards(space, now, limit, local_tz):
    rows = GrantAward.objects.filter(request__event__makerspace=space, state="offered", accept_by__gt=now)
    from datetime import timedelta
    from django.db.models import F
    rows = rows.exclude(request__event__status="cancelled").filter(accept_by__gt=F("offered_at") + timedelta(days=1))
    for row in undiscovered(rows, space=space, award=True).order_by("accept_by", "pk")[:min(limit, 100)]:
        if row.accept_by.timestamp() - 86400 > row.offered_at.timestamp():
            yield ReminderSubject(award_identity(row), "award_accept", row.accept_by, (-86400,))


def discover_claims(space, now, limit, local_tz):
    from django.db.models import Case, When, F, DateTimeField
    rows = ReimbursementClaim.objects.filter(event__makerspace=space, state__in=("draft", "open", "returned_for_info"))
    rows = rows.exclude(event__status="cancelled").annotate(due=Case(When(state="returned_for_info", then=F("info_due_at")),
        default=F("effective_due_at"), output_field=DateTimeField()), activation=Case(
            When(state="returned_for_info", then=F("current_decision__decided_at")), default=F("created_at"),
            output_field=DateTimeField())).filter(due__gt=now)
    from datetime import timedelta
    rows = rows.filter(due__gt=F("activation") + timedelta(days=1))
    for row in undiscovered(rows, space=space, award=False).order_by("due", "pk")[:min(limit, 100)]:
        offsets = tuple(offset for offset in (-604800, -86400) if row.due.timestamp() + offset > row.activation.timestamp())
        if offsets:
            yield ReminderSubject(claim_identity(row), "claim_due", row.due, offsets)


def resolve(space, schedule, now, *, award):
    parts = schedule.subject.split(":")
    if len(parts) < 4 or parts[0] != ("award" if award else "claim") or not parts[1].isdecimal():
        return None
    if award:
        row = GrantAward.objects.filter(pk=int(parts[1]), request__event__makerspace=space, state="offered").first()
        if row is None or award_identity(row) != schedule.subject or row.accept_by != schedule.due_at:
            return None
        event, due = row.request.event, row.accept_by
        offsets = (-86400,)
        activation = row.offered_at
    else:
        row = ReimbursementClaim.objects.filter(pk=int(parts[1]), event__makerspace=space,
            state__in=("draft", "open", "returned_for_info")).first()
        if row is None or claim_identity(row) != schedule.subject:
            return None
        event = row.event
        due = row.info_due_at if row.state == "returned_for_info" else row.effective_due_at
        offsets = (-604800, -86400)
        activation = row.current_decision.decided_at if row.state == "returned_for_info" else row.created_at
    if event.status == "cancelled" or due != schedule.due_at or now >= due or schedule.offset_seconds not in offsets:
        return None
    from datetime import timedelta
    if due + timedelta(seconds=schedule.offset_seconds) <= activation:
        return None
    from apps.makerspaces.platform import module_enabled
    from apps.makerspaces.servability import is_servable
    from apps.notifications.inbox import eligible_owner
    owner_id = row.request.member_id if award else row.member_id
    return row if is_servable(space) and eligible_owner(space, owner_id) and all(
        module_enabled(space, key) for key in ("events", "event_reimbursements")) else None


def build_award(space, schedule, now, local_tz):
    return ReminderMessage("Travel support offer deadline", "reimbursement.award_reminder") if resolve(space, schedule, now, award=True) else None


def build_claim(space, schedule, now, local_tz):
    return ReminderMessage("Travel support claim deadline", "reimbursement.claim_reminder") if resolve(space, schedule, now, award=False) else None


def dispatch(space, schedule, message, now, local_tz, *, award):
    row = resolve(space, schedule, timezone.now(), award=award)
    if row is None:
        return NotificationResult(False)
    envelope = enqueue_locked(row, "award_reminder" if award else "claim_reminder", identity=str(schedule.pk))
    return NotificationResult(envelope is not None, {"envelope": 1} if envelope else {})


def dispatch_award(*args):
    return dispatch(*args, award=True)


def dispatch_claim(*args):
    return dispatch(*args, award=False)


AWARD_REMINDER_SOURCE = ReminderSource("event_reimbursements.award_accept", "event_reimbursements",
    discover_awards, build_award, dispatch=dispatch_award)
CLAIM_REMINDER_SOURCE = ReminderSource("event_reimbursements.claim_due", "event_reimbursements",
    discover_claims, build_claim, dispatch=dispatch_claim)

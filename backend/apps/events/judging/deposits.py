"""Hack-money G10: an optional refundable commitment deposit per hackathon (`events.deposits`, off).

- Raised once on the member when their place is CONFIRMED (`service_payments.create_for_registered_
  registration`, the same seam as a registration charge, so approval events charge on approval and
  never before it, C-34). A crew place never owes one. Subject `event_deposit`, events money.
- A cancelled or rejected place closes it like any programme charge: a pending deposit is voided, a
  paid one gets a refund DUE case for staff to decide (#59). An event cancellation closes them all.
- After the event, staff approve ONE settlement batch. A person who checked in (and submitted, when
  the event requires it) gets a DUE case for the full deposit (`deposit_returned`) and a pending one is
  voided; a no-show keeps the charge (audited `deposit_forfeited`). Money never moves on its own:
  each returned deposit is still a refund case a staff member approves.
"""

from django.utils.translation import gettext
import logging

from django.db import transaction
from django.http import Http404
from django.utils import timezone

from apps.audit.services import record
from .boundary import command, mutation
from .errors import ProgrammeError
from .serializers import CommandInput, validated

logger = logging.getLogger(__name__)
DEPOSITS = "events.deposits"
SUBJECT = "event_deposit"
SETTLED = ("paid_online", "paid_offline")


def deposit_amount(event):
    from apps.payments.availability import charge_tracking_enabled
    from .feature import enabled
    from .options import option
    if not enabled(event.makerspace, DEPOSITS) or not charge_tracking_enabled(event.makerspace, "events"):
        return None
    return option(event, "deposit_amount")


def raise_deposit(registration, actor):
    """Inside the confirming transaction: record the deposit once (None when off or not owed)."""
    if registration.member_id is None or registration.is_crew:
        return None
    amount = deposit_amount(registration.event)
    if not amount:
        return None
    from apps.events.programme_charges import raise_charge
    return raise_charge(event=registration.event, subject_type=SUBJECT, subject_id=registration.pk,
                        member=registration.member, amount=amount, actor=actor, audit_action="event.deposit.raised",
                        target={"type": "registration", "id": registration.pk, "label": "Refundable deposit"})


def close_deposits_after_commit(event, actor, registration_ids):
    """Places cancelled or rejected one by one close their deposits after commit (provider I/O never
    runs under the event lock). An event cancellation passes None: `close_for_cancelled_event` owns it."""
    from apps.payments.models import Payment
    if not registration_ids:
        return
    rows = list(Payment.objects.filter(makerspace=event.makerspace, subject_type=SUBJECT,
                                       subject_id__in=registration_ids, status__in=("pending", *SETTLED))
                .values_list("subject_id", flat=True))
    if rows:
        transaction.on_commit(lambda: _close(event.pk, actor, rows, "registration_cancelled"))


def _close(event_id, actor, subject_ids, reason_code):
    from apps.events.models import Event
    from apps.events.programme_charges import close_charge
    event = Event.objects.select_related("makerspace").get(pk=event_id)
    for subject_id in subject_ids:
        try:
            close_charge(event=event, subject_type=SUBJECT, subject_id=subject_id, actor=actor,
                         reason_code=reason_code, audit_action="event.deposit.closed")
        except Exception:  # one provider outage never strands the others; the refund sweep recovers it
            logger.exception("Deposit close failed", extra={"subject_id": subject_id})


def _came(event, require_submission):
    """Registration ids that count as attended: checked in, and in a submitted project if required."""
    from apps.events.models import EventRegistration, HackathonSubmission
    attended = dict(EventRegistration.objects.filter(event=event, status="attended").values_list("pk", "member_id"))
    if not require_submission:
        return set(attended)
    submitted = set()
    for members in (HackathonSubmission.objects.filter(event_id=event.pk, current_snapshot__isnull=False)
                    .exclude(state="withdrawn").values_list("current_snapshot__sealed_member_ids", flat=True)):
        submitted.update(members or ())
    return {pk for pk, member_id in attended.items() if member_id in submitted}


def plan(event):
    """What the batch would do, one row per deposit: return | void | keep | none (already decided)."""
    from apps.payments.models import Payment, RefundCase
    from .options import option
    came = _came(event, bool(option(event, "deposit_requires_submission")))
    from apps.events.models import EventRegistration
    members = dict(EventRegistration.objects.filter(event=event).values_list("pk", "member_id"))
    rows = []
    for payment in Payment.objects.filter(makerspace=event.makerspace, subject_type=SUBJECT,
                                          subject_id__in=list(members)).order_by("pk"):
        if payment.status not in ("pending", *SETTLED) or RefundCase.objects.filter(payment=payment).exists():
            outcome = "none"
        elif payment.subject_id in came:
            outcome = "return" if payment.status in SETTLED else "void"
        else:
            outcome = "keep"
        rows.append({"payment_id": payment.pk, "registration_id": payment.subject_id,
                     "member_id": members.get(payment.subject_id), "amount": payment.amount,
                     "currency": payment.currency, "payment_status": payment.status, "outcome": outcome})
    return rows


def require_settler(actor, event):
    from .feature import require_capability
    from .payouts import may_record
    require_capability(event, DEPOSITS)
    if not may_record(actor, event.makerspace_id):
        raise Http404


def summary(event, *, actor):
    from .options import option
    require_settler(actor, event)
    return {"event_id": event.pk, "amount": option(event, "deposit_amount"),
            "requires_submission": bool(option(event, "deposit_requires_submission")),
            "settled_at": option(event, "deposits_settled_at"), "event_ended": event.ends_at <= timezone.now(),
            "rows": plan(event)}


def settle(event_id, *, actor, data):
    """Staff approve the batch once, after the event. Only then do refund cases open."""
    from .models_options import HackathonProgrammeOptions
    values = validated(CommandInput, data)
    with mutation(event_id, actor, owner=True) as (event, _):
        require_settler(actor, event)

        def run():
            row = HackathonProgrammeOptions.objects.select_for_update().filter(event=event).first()
            if row is None or not row.deposit_amount:
                raise Http404
            if row.version != values["expected_version"]:
                raise ProgrammeError("stale_version", gettext("This item changed."), current_version=row.version)
            if row.deposits_settled_at is not None:
                raise ProgrammeError("already_settled", gettext("Deposits for this event were already settled."))
            if event.ends_at > timezone.now():
                raise ProgrammeError("event_not_ended", gettext("Settle deposits after the event ends."))
            rows = plan(event)
            for item in rows:
                if item["outcome"] == "keep":
                    record(actor, "event.deposit.forfeited", makerspace=event.makerspace, target=event,
                           meta={"event_id": event.pk, "payment_id": item["payment_id"],
                                 "reason_code": "deposit_forfeited"})
            row.deposits_settled_at = timezone.now()
            row.version += 1
            row.save(update_fields=["deposits_settled_at", "version", "updated_at"])
            counts = {kind: sum(1 for item in rows if item["outcome"] == kind) for kind in ("return", "void", "keep")}
            record(actor, "event.deposit.settled", makerspace=event.makerspace, target=event,
                   meta={"event_id": event.pk, "return": counts["return"], "void": counts["void"],
                         "keep": counts["keep"]})
            closing = [item["registration_id"] for item in rows if item["outcome"] in ("return", "void")]
            if closing:
                transaction.on_commit(lambda: _close(event.pk, actor, closing, "deposit_returned"))
            return {"event_id": event.pk, "amount": row.deposit_amount, "requires_submission":
                    row.deposit_requires_submission, "settled_at": row.deposits_settled_at, "event_ended": True,
                    "rows": rows}
        return command(event, actor, values, path="deposits/settle", run=run)

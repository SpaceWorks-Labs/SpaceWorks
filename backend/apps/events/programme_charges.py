"""L21b: the two hackathon charges, raised on the team leader and closed only by staff decisions.

`raise_charge` records the debt (charge tracking, `charges.events`) and schedules the optional online
checkout, exactly as a registration charge does. `close_charge` is the one seam for "the thing this
charge paid for will not happen": a pending charge is voided (no money ever moved); a paid one opens a
refund DUE case for the full amount and waits for a staff decision (#59). Money never moves here.
"""

import logging
from dataclasses import replace
from decimal import Decimal

from django.db import IntegrityError, transaction

from apps.audit.services import record

logger = logging.getLogger(__name__)
SETTLED = ("paid_online", "paid_offline")
PAID_OR_WAIVED = (*SETTLED, "waived")


def _component(subject_type):
    from apps.payments.pricing.components import Component
    if subject_type == "submission_fee":
        return Component("entry_fee", "Project entry fee", "project", "submission_fee", discountable=False)
    return Component("team_fee", "Team registration", "team", "team_registration", discountable=False)


def _snapshot(event, subject_type, amount, currency, target):
    from apps.payments.pricing.quotes import Quote, line
    item = line(_component(subject_type), currency=currency, quantity=1, unit_amount=Decimal(amount),
                rate_source="event_programme_options", target=target, detail={})
    return Quote(domain="events", currency=currency, lines=(replace(item, discount=Decimal("0")),),
                 mode="paid").to_snapshot()


def find_charge(event, subject_type, subject_id):
    from apps.payments.models import Payment
    return Payment.objects.filter(makerspace=event.makerspace, subject_type=subject_type,
                                  subject_id=subject_id).first()


def raise_charge(*, event, subject_type, subject_id, member, amount, actor, audit_action, target):
    """Record (once) the charge for one project or team. Returns the Payment or None (free/off)."""
    from apps.payments.availability import charge_tracking_enabled, online_payments_enabled
    from apps.payments.models import MakerspacePaymentSettings, Payment
    from apps.payments.services import create_checkout, create_payment
    if not amount or Decimal(amount) <= 0 or not charge_tracking_enabled(event.makerspace, "events"):
        return None
    existing = find_charge(event, subject_type, subject_id)
    if existing is not None:
        return existing  # One charge per project or team: a team that changes size is never re-priced.
    currency = MakerspacePaymentSettings.for_makerspace(event.makerspace).default_currency
    try:
        with transaction.atomic():
            payment = create_payment(
                makerspace=event.makerspace, subject_type=subject_type, subject_id=subject_id, member=member,
                amount=Decimal(amount), currency=currency, created_by=actor or member, subject_label=event.title,
                due_at=event.starts_at, pricing_snapshot=_snapshot(event, subject_type, amount, currency, target))
    except IntegrityError:
        return find_charge(event, subject_type, subject_id)
    record(actor or member, audit_action, makerspace=event.makerspace, target=payment,
           meta={"event_id": event.pk, "payment_id": payment.pk, "subject_type": subject_type})
    if payment.status == Payment.Status.PENDING and online_payments_enabled(event.makerspace, "events"):
        def checkout():
            try:
                create_checkout(payment)
            except Exception:
                logger.error("Programme checkout failed", extra={"payment_id": payment.pk})
        transaction.on_commit(checkout)
    return payment


def settled_or_free(event, subject_type, subject_id):
    """True when no charge is owed or it is paid/waived: the gate a held project or team waits on."""
    payment = find_charge(event, subject_type, subject_id)
    return payment is None or payment.status in (*PAID_OR_WAIVED, "cancelled")


def _has_due_case(payment):
    from apps.payments.models import RefundCase
    return RefundCase.objects.filter(payment=payment, kind=RefundCase.Kind.DUE).exists()


@transaction.atomic
def close_charge(*, event, subject_type, subject_id, actor, reason_code, audit_action, open_due=True):
    """Void a pending charge, or (``open_due``) open a full-amount refund DUE case on a paid one.
    Never refunds: a staff decision on the case does that."""
    from apps.payments.reconciliation import cancel_pending
    from apps.payments.services_refund_partial import add_due_share
    payment = cancel_pending(makerspace=event.makerspace, subject_type=subject_type, subject_id=subject_id,
                             actor=actor)
    if payment is None:
        return None
    case = None
    if payment.status in SETTLED and not open_due:
        return None  # Paid and no refund rule: the charge simply stands.
    if payment.status in SETTLED and _has_due_case(payment):
        return None  # Already assessed once (a disqualification, a closed team): staff own that case.
    if payment.status in SETTLED:
        case = add_due_share(payment, amount=payment.amount, reason_code=reason_code, actor=actor,
                             snapshot={"event_id": event.pk})
    record(actor, audit_action, makerspace=event.makerspace, target=payment,
           meta={"event_id": event.pk, "payment_id": payment.pk, "status": payment.status,
                 "refund_case_id": case.pk if case else None})
    return case


def close_for_cancelled_event(event, actor):
    """Hack-money G1: a cancelled hackathon closes every entry fee and team charge it raised.

    Called inside the cancelling transaction; the work runs after commit, one charge per
    transaction, because voiding a pending charge may expire a live provider checkout and
    provider I/O never runs under the event lock. Pending charges are voided; a settled one
    opens a full-amount DUE case (`event_cancelled`, decision 60) for staff to decide.
    A charge a cohort signal or a disqualification already closed is left alone.
    """
    from apps.events.models import HackathonSubmission, HackathonTeam
    from apps.payments.models import Payment
    owned = {"submission_fee": HackathonSubmission.objects.filter(event_id=event.pk).values("pk"),
             "team_registration": HackathonTeam.objects.filter(event_id=event.pk).values("pk")}
    rows = []
    for subject_type, subjects in owned.items():
        rows += list(Payment.objects.filter(
            makerspace=event.makerspace, subject_type=subject_type, subject_id__in=subjects,
            status__in=(Payment.Status.PENDING, *SETTLED)).values_list("subject_type", "subject_id"))
    if not rows:
        return
    actions = {"submission_fee": "event.submission.fee_closed", "team_registration": "event.team.payment_closed"}
    event_id = event.pk

    def close_all():
        from apps.events.models import Event
        cancelled = Event.objects.select_related("makerspace").get(pk=event_id)
        for subject_type, subject_id in rows:
            try:
                close_charge(event=cancelled, subject_type=subject_type, subject_id=subject_id, actor=actor,
                             reason_code="event_cancelled", audit_action=actions[subject_type])
            except Exception:  # one provider outage never strands the others; the refund sweep recovers it
                logger.exception("Programme charge close failed", extra={"subject_id": subject_id})

    transaction.on_commit(close_all)

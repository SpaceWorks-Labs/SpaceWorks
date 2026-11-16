"""The organiser's approval to charge a linked machine item's cost to the event (decision 342).

Deliberately a RECORD, not a money move. The existing event finance has no account that can absorb a member's
charge: the per-event budget (`EventFinanceBudget`) is a figure to measure spend against, and the
reimbursement pools pay money OUT through awards and decisions. So approving here appends a
`MachineEventCostApproval` (the amount as it stood, the charge it refers to, a note) and never touches the
`Payment`: the member's own charge stands, exactly as raised, until space staff settle it through the ordinary
ledger (a `ManualSettlement` for money received from the event, or a waiver). The event's money view and the
machine-use report show approved totals beside the event budget so staff can do that with the facts in front
of them. Available only while event charges are tracked (`charges.enabled` + `charges.events`).
"""
from django.db import transaction
from django.utils.translation import gettext
from rest_framework.exceptions import NotFound, ValidationError

from apps.audit import services as audit

from . import event_authority, event_permissions
from .machine_use_services import subject_facts
from .models_machine_use import MachineEventCostApproval as Approval, MachineEventLink


def linked_subject(link):
    return link.session or link.service_request or link.booking


def charge_for(link):
    """The member's charge for the linked item, or None when it carries none."""
    from apps.payments.models import Payment
    subject = linked_subject(link)
    kind = (Payment.SubjectType.MACHINE_SESSION if link.session_id else Payment.SubjectType.BOOKING if link.booking_id
            else Payment.SubjectType.MACHINE_SERVICE_REQUEST)
    return Payment.objects.filter(makerspace_id=link.makerspace_id, subject_type=kind, subject_id=subject.pk).first()


def latest_decision(link):
    return link.cost_approvals.first()


def finance_on(space):
    from apps.payments.availability import charge_tracking_enabled
    return charge_tracking_enabled(space, "events")


@transaction.atomic
def decide(actor, event, link_id, decision, note=""):
    """Append the organiser's decision for one link of `event`. Idempotent: repeating the latest changes nothing."""
    if not event_authority.can(actor, event, event_permissions.EDIT_DETAILS):
        raise NotFound()
    link = MachineEventLink.objects.select_for_update().filter(pk=link_id, event=event).first()
    if link is None:
        raise NotFound()
    if not finance_on(event.makerspace):
        raise ValidationError({"detail": gettext("Event charges are not tracked in this makerspace."),
                               "code": "event_finance_off"})
    latest = latest_decision(link)
    if (latest.decision if latest else Approval.Decision.WITHDRAWN) == decision:
        return latest
    payment = charge_for(link) if decision == Approval.Decision.APPROVED else (latest.payment if latest else None)
    row = Approval.objects.create(
        makerspace_id=link.makerspace_id, link=link, decision=decision, note=note[:300], payment=payment,
        amount=payment.amount if payment else None, currency=payment.currency if payment else "")
    subject = linked_subject(link)
    _space, _type, _person, kwargs = subject_facts(subject)
    meta = {"link_id": link.pk, "event_id": event.pk, "payment_id": payment.pk if payment else None,
            "amount": str(row.amount) if row.amount is not None else None, "currency": row.currency,
            {"session": "session_id", "booking": "booking_id"}.get(next(iter(kwargs)), "service_request_id"): subject.pk}
    if decision == Approval.Decision.APPROVED:
        audit.record(actor, "machine_event.cost_approved", makerspace=event.makerspace, target=link, meta=meta)
    else:
        audit.record(actor, "machine_event.cost_withdrawn", makerspace=event.makerspace, target=link, meta=meta)
    return row

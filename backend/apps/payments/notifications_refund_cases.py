"""Refund-case notices: staff hear about new cases, the member hears the decision.

`refund_due_opened` and `refund_request_received` go to staff only;
`refund_request_approved` and `refund_request_declined` go to the payer only.
`refund_issued` (payments.ledger) still fires separately once the money settles.
Rendered through the existing `payments` templates; the decision note itself is read
in the member area, never placed in a notification body.
"""

from apps.integrations.email_templates_registry_helpers import bag
from apps.integrations.notification_links import payment_link
from apps.integrations.notification_sources import NotificationSource, register_source
from apps.operations.notifications_p2 import fanout, revision, safe_notification, scoped, staff_link, template

from .models import RefundCase

CASE_SOURCE = "payments.refund_case"
STAFF_EVENTS = frozenset({"refund_due_opened", "refund_request_received", "refund_approval_failed"})
MEMBER_EVENTS = frozenset({"refund_request_approved", "refund_request_declined"})
EVENTS = STAFF_EVENTS | MEMBER_EVENTS
_STATUS = {
    "refund_due_opened": RefundCase.ACTIVE_STATUSES,
    "refund_request_received": RefundCase.ACTIVE_STATUSES,
    # Parity B20: the provider refused an approved refund; staff retry or decline.
    "refund_approval_failed": (RefundCase.Status.APPROVAL_FAILED,),
    "refund_request_approved": (RefundCase.Status.APPROVED,),
    "refund_request_declined": (RefundCase.Status.DECLINED,),
}


def case_revision(case, event):
    if event == "refund_approval_failed":
        # One notice per refused attempt: a retry that is refused again is new news.
        return revision(case.pk, event, case.refund_id)
    marker = case.decided_at if event in MEMBER_EVENTS else (case.requested_by_id if event ==
                                                             "refund_request_received" else case.due_amount)
    return revision(case.pk, event, marker)


def _row(envelope):
    return scoped(RefundCase, envelope.makerspace_id, field="payment__makerspace_id").select_related(
        "payment__makerspace", "payment__member").filter(pk=envelope.source_id).first()


def _subject(case, audience):
    payment = case.payment
    staff = {"id": payment.pk, "status": str(case.status)[:160]}
    if audience == "staff":
        return bag(**staff)
    amount = case.approved_amount if case.approved_amount is not None else case.due_amount
    return bag(**staff, amount=str(amount)[:32], currency=str(payment.currency or "")[:8], due_date="")


def _rendered(case, event, audience):
    space = case.payment.makerspace
    return template(space, "payments", audience, event,
        {"makerspace": bag(name=space.name), "event_name": event, "subject": _subject(case, audience)},
        link=payment_link(space) if audience != "staff" else staff_link(space, "payments"))


def eligible(envelope):
    case = _row(envelope)
    if case is None or envelope.event not in EVENTS or case.status not in _STATUS[envelope.event]:
        return False
    if envelope.event in STAFF_EVENTS and envelope.audience != "staff":
        return False
    if envelope.event in MEMBER_EVENTS and (envelope.audience == "staff"
                                            or case.payment.member_id != envelope.recipient_id):
        return False
    return envelope.revision == case_revision(case, envelope.event)


def render(envelope):
    case = _row(envelope)
    return _rendered(case, envelope.event, envelope.audience)


@safe_notification
def notify_refund_case(case, event):
    if event not in EVENTS:
        raise ValueError("Unknown refund case notification event")
    space = case.payment.makerspace
    member_event = event in MEMBER_EVENTS
    return fanout(row=case, space=space, feature="payments", stream="payments", event=event,
        source_kind=CASE_SOURCE, revision=case_revision(case, event),
        owner=case.payment.member if member_event else None,
        owner_body=_rendered(case, event, "requester") if member_event else None,
        staff_body=_rendered(case, event, "staff"), staff=not member_event,
        context={"case_id": case.pk, "payment_id": case.payment_id},
        owner_context={"makerspace": bag(name=space.name), "event_name": event,
                       "subject": _subject(case, "requester")},
        staff_context={"makerspace": bag(name=space.name), "event_name": event,
                       "subject": _subject(case, "staff")})


def register():
    register_source(CASE_SOURCE, NotificationSource(eligible, render))

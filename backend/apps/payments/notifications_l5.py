"""Lane L5 notices: staff hear about claims, held captures and disputes; the payer hears
the claim decision. Rendered through the generic `payments` templates, so no amount,
reference or note reaches a staff chat room -- staff read those in the console.
"""

from apps.integrations.email_templates_registry_helpers import bag
from apps.integrations.notification_links import payment_link
from apps.integrations.notification_sources import NotificationSource, register_source
from apps.operations.notifications_p2 import fanout, revision, safe_notification, scoped, staff_link, template

SOURCE = "payments.l5"
STAFF_EVENTS = frozenset({"paid_claim_received", "settlement_awaiting_confirmation", "capture_flagged",
                          "dispute_opened"})
MEMBER_EVENTS = frozenset({"paid_claim_confirmed", "paid_claim_rejected"})


def _payment(envelope):
    from .models import Payment
    return scoped(Payment, envelope.makerspace_id).select_related("makerspace", "member").filter(
        pk=envelope.context.get("payment_id")).first()


def _rendered(payment, event, audience):
    space = payment.makerspace
    subject = {"id": payment.pk, "status": str(payment.status)[:160]}
    if audience != "staff":
        subject.update(amount=str(payment.amount)[:32], currency=str(payment.currency)[:8], due_date="")
    return template(space, "payments", audience, event,
        {"makerspace": bag(name=space.name), "event_name": event, "subject": bag(**subject)},
        link=payment_link(space) if audience != "staff" else staff_link(space, "payments"))


def eligible(envelope):
    payment = _payment(envelope)
    if payment is None or envelope.event not in STAFF_EVENTS | MEMBER_EVENTS:
        return False
    if envelope.event in STAFF_EVENTS:
        return envelope.audience == "staff"
    return envelope.audience != "staff" and payment.member_id == envelope.recipient_id


def render(envelope):
    return _rendered(_payment(envelope), envelope.event, envelope.audience)


def _notify(payment, row, event, marker):
    member_event = event in MEMBER_EVENTS
    space = payment.makerspace
    return fanout(row=row, space=space, feature="payments", stream="payments", event=event, source_kind=SOURCE,
        revision=revision(type(row).__name__, row.pk, event, marker),
        owner=payment.member if member_event else None,
        owner_body=_rendered(payment, event, "requester") if member_event else None,
        staff_body=_rendered(payment, event, "staff"), staff=not member_event,
        context={"payment_id": payment.pk, "row_kind": type(row).__name__},
        owner_context={"makerspace": bag(name=space.name), "event_name": event},
        staff_context={"makerspace": bag(name=space.name), "event_name": event})


@safe_notification
def notify_claim(claim, event):
    return _notify(claim.payment, claim, event, claim.decided_at or claim.created_at)


@safe_notification
def notify_confirmation(confirmation):
    return _notify(confirmation.payment, confirmation, "settlement_awaiting_confirmation", confirmation.created_at)


@safe_notification
def notify_capture_flag(flag):
    return _notify(flag.payment, flag, "capture_flagged", flag.flagged_at)


@safe_notification
def notify_dispute(dispute):
    return _notify(dispute.payment, dispute, "dispute_opened", dispute.opened_at)


def register():
    register_source(SOURCE, NotificationSource(eligible, render))

"""Ledger-backed personal notices, independent of the removable payment rail."""
from django.utils import timezone

from apps.integrations.notification_links import local_link
from apps.integrations.email_templates_registry_helpers import bag
from apps.integrations.notification_sources import NotificationSource, register_source
from apps.operations.notifications_p2 import body, direct_mail_unless_routed, fanout, revision, safe_notification, scoped, staff_link, template
from .models import Payment, PaymentDocument, Refund

PAYMENT_SOURCE = "payments.ledger"
DOCUMENT_SOURCE = "payments.document"
OWNER_ONLY = {"payment_due_soon", "payment_due_today", "payment_overdue", "payment_failed"}
EVENTS = OWNER_ONLY | {"charge_raised", "payment_received", "refund_issued"}


def financial_revision(payment, event, refund=None, reminder=None, occurrence=None):
    """Also used by the loan lane: the ledger owns the one charge identity."""
    if refund:
        return revision(payment.pk, "refund", refund.pk, refund.settled_at)
    if reminder:
        return revision(payment.pk, "reminder", reminder.pk)
    if occurrence is not None:
        return revision(payment.pk, event, occurrence)
    # Checkout/provider claims do not create a new debt or a new receipt.
    return revision(payment.pk, event, payment.created_at)


def _row(envelope):
    return scoped(Payment, envelope.makerspace_id).select_related("makerspace", "member").filter(
        pk=envelope.source_id,
    ).first()


def _refund(envelope, payment):
    refund_id = envelope.context.get("refund_id")
    return scoped(Refund, payment.makerspace_id, field="payment__makerspace_id").filter(
        pk=refund_id, payment=payment, status="succeeded", amended_by__isnull=True,
    ).first() if refund_id else None


def eligible(envelope):
    payment = _row(envelope)
    if payment is None or envelope.event not in EVENTS:
        return False
    if envelope.audience != "staff" and payment.member_id != envelope.recipient_id:
        return False
    if envelope.event in OWNER_ONLY | {"charge_raised"} and payment.status != "pending":
        return False
    if envelope.event in {"payment_received", "refund_issued"} and payment.status not in {"paid_online", "paid_offline"}:
        return False
    refund = _refund(envelope, payment)
    if envelope.event == "refund_issued" and refund is None:
        return False
    if envelope.event == "payment_failed" and envelope.context.get("occurrence"):
        from apps.audit.models import AuditLog
        if not scoped(AuditLog, payment.makerspace_id).filter(
            pk=envelope.context["occurrence"], action="payment.failed",
            target_type="payments.payment", target_id=str(payment.pk),
        ).exists():
            return False
    reminder = None
    if envelope.context.get("reminder_id"):
        from apps.operations.models_reminders import ReminderSchedule
        from .reminders import _current_payment
        reminder = scoped(ReminderSchedule, payment.makerspace_id).filter(
            pk=envelope.context["reminder_id"], source="payments.due",
        ).first()
        if reminder is None or _current_payment(payment.makerspace, reminder, timezone.now()) is None:
            return False
    return envelope.revision == financial_revision(payment, envelope.event, refund, reminder,
                                                   envelope.context.get("occurrence"))


def rendered(payment, event, audience, refund=None):
    from apps.makerspaces.local_time import to_local
    subject = bag(id=payment.pk, status=payment.status)
    if audience != "staff":
        subject = bag(id=payment.pk, status=payment.status,
            amount=str(refund.amount if refund else payment.amount), currency=payment.currency,
            due_date=to_local(payment.makerspace, payment.due_at).date().isoformat() if payment.due_at else "")
    return template(payment.makerspace, "payments", audience, event,
        {"makerspace": bag(name=payment.makerspace.name), "event_name": event, "subject": subject},
        link=local_link(payment.makerspace, "member") if audience != "staff" else staff_link(payment.makerspace, "payments"))


def render(envelope):
    payment = _row(envelope)
    return rendered(payment, envelope.event, envelope.audience, _refund(envelope, payment))


@safe_notification
def notify_payment(payment, event, *, refund=None, requester_only=False, reminder=None, occurrence=None):
    if event not in EVENTS:
        raise ValueError("Unknown ledger notification event")
    return fanout(row=payment, space=payment.makerspace, feature="payments", stream="payments",
        event=event, source_kind=PAYMENT_SOURCE,
        revision=financial_revision(payment, event, refund, reminder, occurrence),
        owner=payment.member, owner_body=rendered(payment, event, "requester", refund),
        staff_body=rendered(payment, event, "staff"), staff=not requester_only and event not in OWNER_ONLY,
        context={"refund_id": refund.pk if refund else None, "reminder_id": reminder.pk if reminder else None,
                 "occurrence": str(occurrence) if occurrence is not None else None},
        staff_context={"makerspace": bag(name=payment.makerspace.name), "event_name": event,
                       "subject": bag(id=payment.pk, status=payment.status)})


def document_eligible(envelope):
    document = scoped(PaymentDocument, envelope.makerspace_id).select_related("payment").filter(
        pk=envelope.source_id,
    ).first()
    return bool(document and document.payment.member_id == envelope.recipient_id
                and envelope.event == "document_issued"
                and envelope.revision == revision(document.pk, document.issued_at))


def document_body(document):
    from django.utils.html import format_html
    from apps.makerspaces.website_directory import public_url
    navigation = public_url(document.makerspace, "member", "").rstrip("/")
    text = (f"Your {document.get_kind_display().lower()} {document.number} is available.\n"
            f"{document.currency.upper()} {document.amount}\nSign in to download the PDF: {navigation}")
    return body(f"{document.get_kind_display()} {document.number}", text,
        local_link(document.makerspace, "member"),
        str(format_html('<p>{}</p><p><a href="{}">Download your document</a></p>', text, navigation)))


def render_document(envelope):
    return document_body(scoped(PaymentDocument, envelope.makerspace_id).select_related(
        "makerspace", "payment__member",
    ).get(pk=envelope.source_id))


@safe_notification
def notify_document(document):
    version = revision(document.pk, document.issued_at)
    owner = document.payment.member
    result = fanout(row=document, space=document.makerspace, feature="payments", stream="payments",
        event="document_issued", source_kind=DOCUMENT_SOURCE, revision=version,
        owner=owner, owner_body=document_body(document), staff=False)
    if owner is not None:
        # The document email was a direct, matrix-independent payer mail.
        own = document_body(document)
        direct_mail_unless_routed(space=document.makerspace, source_kind=DOCUMENT_SOURCE, row=document,
            revision=version, event="document_issued", owner=owner, to_email=owner.email,
            subject=own["subject"], text=own["text"], stream="payments",
            audience="requester", feature="", sync=True, persist_body=False, address_owner=False)
    return result


def register():
    register_source(PAYMENT_SOURCE, NotificationSource(eligible, render))
    register_source(DOCUMENT_SOURCE, NotificationSource(document_eligible, render_document))

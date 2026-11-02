"""Source-backed hardware lifecycle and financial notices."""
from apps.integrations.notification_links import local_link
from apps.accounts import rbac
from apps.integrations.email_templates import hardware_context, render
from apps.integrations.notification_sources import NotificationSource, register_source
from apps.hardware_requests.notifications_p2 import safe_adapter
from .models import HardwareRequest
from .notifications_p2 import content, fanout, revision

KIND = "hardware.request"
KEYS = {"submitted": "request_received", "accepted": "request_accepted",
        "rejected": "request_rejected", "issued": "request_issued",
        "partially_returned": "request_returned", "returned": "request_returned",
        "closed_with_issue": "request_returned", "return_reminder": "return_reminder"}


def request_revision(row):
    return revision(row.status, row.updated_at, row.return_due_at)


def eligible(envelope):
    row = rbac.scope_notification_policy(HardwareRequest.objects.all(),
        makerspace_id=envelope.makerspace_id).select_related("requester").filter(pk=envelope.source_id).first()
    if row is None:
        return False
    if envelope.event == "return_reminder":
        valid = row.status in {"issued", "partially_returned"} and row.return_due_at is not None
        valid = valid and row.return_due_at.isoformat() == envelope.context.get("due_at")
    else:
        valid = request_revision(row) == envelope.revision
        valid = valid and row.status == {"submitted": "pending_approval"}.get(envelope.event, envelope.event)
    if envelope.audience == "requester":
        valid = valid and row.requester_id == envelope.recipient_id and not row.anonymous_idempotency_key_fingerprint
        from .notifications_p2_email import source_ready
        valid = valid and source_ready(envelope)
    actor_id = envelope.context.get("actor_id")
    if actor_id:
        from apps.accounts.models import User
        actor = User.objects.filter(pk=actor_id).first()
        action = {"accepted": rbac.Action.ACCEPT_REQUEST, "rejected": rbac.Action.REJECT_REQUEST,
                  "issued": rbac.Action.ISSUE_REQUEST}.get(envelope.event, rbac.Action.RETURN_REQUEST)
        if envelope.event == "submitted":
            valid = valid and actor is not None and actor.is_active and actor.access_status == "active"
        else:
            valid = valid and actor is not None and rbac.can(actor, action, row.makerspace_id)
    return bool(valid)


@safe_adapter
def notify_request(row, event, room_text=None):
    type(row).objects.select_for_update().get(pk=row.pk)
    own = render(row.makerspace, "hardware", "requester", KEYS[event], hardware_context(row, staff=False))
    # Bearer URLs are never channel content. All account delivery navigates to the
    # authenticated member page; existing templates keep their editable wording.
    link = local_link(row.makerspace, "member")
    staff_context = hardware_context(row, staff=True)
    staff = render(row.makerspace, "hardware", "staff", event, staff_context)
    summary = room_text(row) if room_text else (
        f"Hardware request #{row.pk} {event.replace('_', ' ')}. Review in the staff console.")
    context = {"request_id": row.pk}
    if event != "return_reminder":
        from apps.audit.models import AuditLog
        audit = rbac.scope_notification_policy(AuditLog.objects.all(), makerspace_id=row.makerspace_id).filter(
            target_type=row._meta.label_lower, target_id=str(row.pk), action=f"request.{event}",
        ).order_by("-pk").first()
        actor_id = audit.actor_id if audit else {
            "submitted": row.requester_id, "accepted": row.accepted_by_id,
            "issued": row.issued_by_id, "returned": row.closed_by_id,
        }.get(event)
        context["actor_id"] = actor_id
    if row.return_due_at:
        context["due_at"] = row.return_due_at.isoformat()
    from .notifications_p2_contact import notify
    contact = notify(row, event, own)
    result = fanout(space=row.makerspace, feature="hardware_requests", stream="hardware",
        event=event, kind=KIND, source=row.pk, version=request_revision(row), subject=row,
        owner=row.requester if not row.anonymous_idempotency_key_fingerprint else None,
        own=content(own, link=link), staff=content(staff), room_body=summary, context=context, staff_context=staff_context)
    from apps.integrations.notify import NotificationResult
    return NotificationResult(result.scheduled or bool(contact and contact.status != "skipped"))


#: Loan charge event -> (subject type, label). Lane L15 adds rental, damage and lost.
CHARGE_EVENTS = {
    "deposit_raised": ("loan_deposit", "Loan deposit"),
    "late_fee_raised": ("loan_late_fee", "Late return fee"),
    "rental_raised": ("loan_rental", "Loan rental"),
    "damage_charged": ("loan_damage", "Damage charge"),
    "lost_charged": ("loan_lost", "Lost item charge"),
}


def _charge_request_id(payment):
    """The loan a charge belongs to: its subject, or (damage/lost) its accountability row's loan."""
    if payment.subject_type in ("loan_damage", "loan_lost"):
        from .models import RequesterAccountability
        return RequesterAccountability.objects.filter(pk=payment.subject_id).values_list("request_id", flat=True).first()
    return payment.subject_id


def eligible_charge(envelope):
    from apps.payments.models import Payment
    payment = rbac.scope_notification_policy(Payment.objects.all(),
        makerspace_id=envelope.makerspace_id).filter(pk=envelope.source_id).first()
    if payment is None or payment.status not in {"pending", "paid_online", "paid_offline"}:
        return False
    if revision(payment.created_at, payment.subject_type, payment.subject_id) != envelope.revision:
        return False
    expected = CHARGE_EVENTS.get(envelope.event, (None,))[0]
    request_id = _charge_request_id(payment)
    return bool(envelope.audience == "staff" and expected == payment.subject_type
                and request_id == envelope.context.get("request_id")
                and rbac.scope_notification_policy(HardwareRequest.objects.all(),
                    makerspace_id=envelope.makerspace_id).filter(pk=request_id).exists())


@safe_adapter
def notify_charge(row, event, payment):
    """Staff-only domain summary. The owner's single charge notice belongs to the
    payment ledger: `payments.services.create_payment` already raises
    `charge_raised` for every loan charge, so a second owner intent here would
    duplicate it."""
    label = CHARGE_EVENTS[event][1]
    version = revision(payment.created_at, payment.subject_type, payment.subject_id)
    return fanout(space=row.makerspace, feature="hardware_requests", stream="hardware",
        event=event, kind="hardware.charge", source=payment.pk, version=version, subject=payment,
        context={"request_id": row.pk, "payment_id": payment.pk},
        staff_context=hardware_context(row, staff=True),
        staff={"subject": label, "text": f"Hardware request #{row.pk}: {label.lower()} raised."})


def eligible_waiver(envelope):
    from apps.payments.models import LoanFeeWaiver
    waiver = rbac.scope_notification_policy(LoanFeeWaiver.objects.all(),
        makerspace_id=envelope.makerspace_id).filter(pk=envelope.source_id, revokes__isnull=True).first()
    return bool(envelope.audience == "staff" and waiver is not None
                and waiver.request_id == envelope.context.get("request_id")
                and revision(waiver.created_at, waiver.request_id) == envelope.revision)


@safe_adapter
def notify_waiver(row, waiver):
    """Staff-only: a loan's fees were waived (lane L15, A14). The reason stays in the audit log."""
    return fanout(space=row.makerspace, feature="hardware_requests", stream="hardware",
        event="fees_waived", kind="hardware.fee_waiver", source=waiver.pk,
        version=revision(waiver.created_at, waiver.request_id), subject=waiver,
        context={"request_id": row.pk, "waiver_id": waiver.pk},
        staff_context=hardware_context(row, staff=True),
        staff={"subject": "Loan fees waived", "text": f"Hardware request #{row.pk}: loan fees waived."})


def register():
    register_source(KIND, NotificationSource(eligible))
    register_source("hardware.charge", NotificationSource(eligible_charge))
    register_source("hardware.fee_waiver", NotificationSource(eligible_waiver))
    from .notifications_p2_contact import register_source as register_contact
    register_contact()
    from .notifications_loans import register as register_loans
    register_loans()

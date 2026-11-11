"""Decision 242(b): a manual payment reminder from the charge's owner, for their own area's charge.

The scheduled reminders (`reminders.py`) are the Space Manager's billing setting. This is the desk's
one-off nudge. Authority is `_require_record_authority` (the subject owner), the email is idempotent per
local day through the notification dedup key, and an account-less charge has nobody to remind.
"""

from django.utils import timezone
from django.utils.translation import gettext
from rest_framework.exceptions import NotFound

from apps.audit import services as audit
from apps.payments.models import Payment
from apps.payments.pay_links import PayLinkRefused


def send_reminder(*, actor, makerspace_id, payment_id):
    from apps.operations.notifications_p2 import direct_mail_unless_routed
    from apps.payments.reconciliation import _require_record_authority

    payment = Payment.objects.select_related("makerspace", "member").filter(
        pk=payment_id, makerspace_id=makerspace_id).first()
    if payment is None:
        raise NotFound(gettext("Payment not found."))
    _require_record_authority(actor, [payment])
    if payment.status != Payment.Status.PENDING:
        raise PayLinkRefused("Only a pending charge can be reminded.", "payment_terminal")
    if payment.member is None or not payment.member.email:
        raise PayLinkRefused("This charge has no account email to remind.", "reminder_no_recipient")
    space = payment.makerspace
    label = payment.subject_label or payment.get_subject_type_display()
    text = gettext("{space} is waiting for {currency} {amount} for {label}. Please pay or reply to this message.").format(
        space=space.name, currency=payment.currency.upper(), amount=payment.amount, label=label)
    direct_mail_unless_routed(
        space=space, source_kind="payments.manual_reminder", row=payment,
        revision=f"manual:{timezone.localdate()}", event="manual_reminder", owner=None,
        to_email=payment.member.email, subject=gettext("Payment reminder from {name}").format(name=space.name),
        text=text, stream="payments", audience="requester", feature="", persist_body=False, address_owner=False)
    audit.record(actor, "payment.manual_reminder_sent", makerspace=space, target=payment,
                 meta={"channel": "email"})
    return payment

"""Secure pay links for account-less charges staff raised (lane L5, X19).

Rules: the charge is pending, belongs to no account, and was raised by a member of staff
of the space; the link is signed by possession of a 256-bit random token (only its
SHA-256 is stored), expires (14 days by default, 60 at most), names exactly one charge,
and shows nothing about who owes it. Registration is NOT payable this way: event
registration still requires an account (Hard Rule), so its charges always have one.
"""

from django.utils.translation import gettext
import hashlib
import secrets
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.accounts import rbac
from apps.audit import services as audit
from apps.payments.models import Payment, PaymentPayLink
from apps.payments.reconciliation import PaymentConflict

DEFAULT_DAYS = 14
MAX_DAYS = 60


class PayLinkRefused(PaymentConflict):
    def __init__(self, detail, code):
        self.detail = {"detail": detail, "code": code}


def digest(token):
    return hashlib.sha256(str(token or "").encode()).hexdigest()


def link_url(token):
    base = (settings.PUBLIC_APP_BASE_URL or "http://localhost:5000").rstrip("/")
    return f"{base}/pay/{token}"


def completion_url():
    base = (settings.PUBLIC_APP_BASE_URL or "http://localhost:5000").rstrip("/")
    return f"{base}/pay/complete"


def _raised_by_staff(payment):
    """The charge's creator holds staff authority here (any action beyond the Member role)."""
    from apps.makerspaces.roles import MEMBER_ROLE_DEFINITION

    creator = payment.created_by
    if creator is None:
        return False
    return bool(rbac.effective_actions(creator, payment.makerspace_id) - set(MEMBER_ROLE_DEFINITION[2]))


@transaction.atomic
def create_link(*, actor, makerspace_id, payment_id, days=DEFAULT_DAYS, email=""):
    from apps.payments.reconciliation import _require_record_authority

    payment = Payment.objects.select_for_update(of=("self",)).select_related("makerspace", "created_by").filter(
        pk=payment_id, makerspace_id=makerspace_id).first()
    if payment is None:
        from rest_framework.exceptions import NotFound
        raise NotFound(gettext("Payment not found."))
    _require_record_authority(actor, [payment])
    if payment.status != Payment.Status.PENDING:
        raise PayLinkRefused("Only a pending charge can be paid by link.", "payment_terminal")
    if payment.member_id is not None:
        raise PayLinkRefused("This charge belongs to an account; the payer signs in to pay it.", "pay_link_has_account")
    if not _raised_by_staff(payment):
        raise PayLinkRefused("Pay links are only for charges staff raised.", "pay_link_not_staff_raised")
    now = timezone.now()
    PaymentPayLink.objects.filter(payment=payment, revoked_at__isnull=True).update(revoked_at=now)
    token = secrets.token_urlsafe(32)
    link = PaymentPayLink.objects.create(
        makerspace=payment.makerspace, payment=payment, token_digest=digest(token), created_by=actor,
        expires_at=now + timedelta(days=max(1, min(int(days), MAX_DAYS))))
    audit.record(actor, "payment.pay_link_created", makerspace=payment.makerspace, target=payment,
                 meta={"pay_link_id": link.pk, "emailed": bool(email)})
    if email:
        _send(payment, token, email, link)
    return link, token


def _send(payment, token, email, link):
    from apps.operations.notifications_p2 import direct_mail_unless_routed

    space = payment.makerspace
    text = (f"{space.name} has asked you to pay {payment.currency.upper()} {payment.amount} "
            f"for {payment.subject_label or payment.get_subject_type_display()}.\n"
            f"Pay securely here: {link_url(token)}\nThis link expires on {link.expires_at.date().isoformat()}.")
    direct_mail_unless_routed(space=space, source_kind="payments.pay_link", row=link, revision=str(link.pk),
                              event="pay_link_sent", owner=None, to_email=email,
                              subject=gettext('Payment request from {name}').format(name=space.name), text=text, stream="payments",
                              audience="requester", feature="", persist_body=False, address_owner=False)


def resolve(token):
    """The live link for a token, or None. Expired, revoked or settled links resolve to None."""
    if not token or len(token) > 128:
        return None
    link = PaymentPayLink.objects.select_related("payment__makerspace").filter(
        token_digest=digest(token), revoked_at__isnull=True, expires_at__gt=timezone.now()).first()
    if link is None or link.payment.member_id is not None:
        return None
    return link


def mark_used(link):
    first = link.last_used_at is None
    PaymentPayLink.objects.filter(pk=link.pk).update(last_used_at=timezone.now())
    if first:
        audit.record(None, "payment.pay_link_used", makerspace=link.payment.makerspace, target=link.payment,
                     meta={"pay_link_id": link.pk})

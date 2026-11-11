"""The payer's "I've paid" claim and the staff decision on it (lane L5, G23).

A claim is a message, not money: confirming it is the staff member recording an offline
settlement (method + the claimed reference + the claimed date) in the same transaction
that marks the charge paid -- or, under maker-checker, proposing it for a second person.
"""

from django.utils.translation import gettext
import re
from datetime import datetime, time

from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.exceptions import APIException, NotFound

from apps.audit import services as audit
from apps.payments.models import Payment, PaymentClaim

REFERENCE = re.compile(r"^[A-Z0-9][A-Z0-9-]{5,34}$")


class ClaimConflict(APIException):
    status_code = 409

    def __init__(self, detail, code):
        self.detail = {"detail": detail, "code": code}


def normalize_reference(value):
    reference = re.sub(r"\s+", "", str(value or "")).upper()
    if not REFERENCE.fullmatch(reference):
        raise ClaimConflict(gettext("Enter the 6-35 character transaction reference (UTR) from your bank or UPI app."),
                            "claim_reference_invalid")
    return reference


@transaction.atomic
def submit_claim(payment, *, claimant, reference, paid_on, method=PaymentClaim.Method.UPI, pay_link=None):
    locked = Payment.objects.select_for_update(of=("self",)).select_related("makerspace").get(pk=payment.pk)
    if locked.status != Payment.Status.PENDING:
        raise ClaimConflict(gettext("This charge is no longer waiting for payment."), "payment_terminal")
    from apps.makerspaces.local_time import local_now
    if paid_on > local_now(locked.makerspace).date():
        raise ClaimConflict(gettext("The payment date cannot be in the future."), "claim_date_invalid")
    reference = normalize_reference(reference)
    if PaymentClaim.objects.filter(makerspace=locked.makerspace, reference=reference).exists():
        raise ClaimConflict(gettext("This reference has already been claimed."), "claim_exists")
    if PaymentClaim.objects.filter(payment=locked, status__in=PaymentClaim.OPEN_STATUSES).exists():
        raise ClaimConflict(gettext("A claim for this charge is already waiting for staff."), "claim_exists")
    try:
        with transaction.atomic():
            claim = PaymentClaim.objects.create(
                makerspace=locked.makerspace, payment=locked, claimant=claimant, pay_link=pay_link, method=method,
                reference=reference, paid_on=paid_on, amount=locked.amount, currency=locked.currency)
    except IntegrityError:
        raise ClaimConflict(gettext("This reference has already been claimed."), "claim_exists")
    audit.record(claimant, "payment.paid_claim_submitted", makerspace=locked.makerspace, target=locked,
                 meta={"claim_id": claim.pk, "method": claim.method, "via_pay_link": pay_link is not None})
    from apps.payments.notifications_l5 import notify_claim
    transaction.on_commit(lambda: notify_claim(claim, "paid_claim_received"))
    return claim


def _locked_claim(makerspace_id, claim_id):
    claim = PaymentClaim.objects.filter(pk=claim_id, makerspace_id=makerspace_id).first()
    if claim is None:
        raise NotFound(gettext("Claim not found."))
    Payment.objects.select_for_update(of=("self",)).get(pk=claim.payment_id)
    claim = PaymentClaim.objects.select_for_update().select_related("payment__makerspace").get(pk=claim.pk)
    if claim.status != PaymentClaim.Status.SUBMITTED:
        raise ClaimConflict(gettext("This claim has already been decided."), "claim_decided")
    return claim


def received_at(claim):
    """The claimed transfer date as an aware instant at the space's local noon."""
    from zoneinfo import ZoneInfo
    return datetime.combine(claim.paid_on, time(12, 0), tzinfo=ZoneInfo(claim.payment.makerspace.timezone or "UTC"))


@transaction.atomic
def confirm_claim(*, actor, makerspace_id, claim_id):
    from apps.payments.reconciliation import reconcile_payments

    claim = _locked_claim(makerspace_id, claim_id)
    settlement = {"method": claim.method, "reference": claim.reference, "received_at": received_at(claim)}
    from apps.payments.maker_checker import propose, requires_confirmation
    payment = claim.payment
    if requires_confirmation(payment.makerspace):
        from apps.payments.reconciliation import PaymentConflict, _require_record_authority
        _require_record_authority(actor, [payment])
        if payment.status != Payment.Status.PENDING:
            raise PaymentConflict([payment.pk])
        propose([payment], actor, settlement, claim=claim)
        claim.status = PaymentClaim.Status.AWAITING_CONFIRMATION
        claim.save(update_fields=["status"])
        audit.record(actor, "payment.paid_claim_confirmed", makerspace=payment.makerspace, target=payment,
                     meta={"claim_id": claim.pk, "awaiting_confirmation": True})
        return claim
    from apps.payments.settlement_supersede import keeping
    with keeping(claim_id=claim.pk):
        reconcile_payments(actor=actor, makerspace_id=makerspace_id, payment_ids=[payment.pk],
                           target_status=Payment.Status.PAID_OFFLINE, settlement=settlement)
    return finish_claim(claim, actor, confirmed=True)


@transaction.atomic
def reject_claim(*, actor, makerspace_id, claim_id, note=""):
    from apps.payments.reconciliation import _require_record_authority

    claim = _locked_claim(makerspace_id, claim_id)
    _require_record_authority(actor, [claim.payment])
    return finish_claim(claim, actor, confirmed=False, note=note)


def finish_claim(claim, actor, *, confirmed, note=""):
    claim.status = PaymentClaim.Status.CONFIRMED if confirmed else PaymentClaim.Status.REJECTED
    claim.decided_by, claim.decided_at = actor, timezone.now()
    claim.decision_note = (note or "").strip()[:300]
    claim.save(update_fields=["status", "decided_by", "decided_at", "decision_note"])
    payment = claim.payment
    if confirmed:
        audit.record(actor, "payment.paid_claim_confirmed", makerspace=payment.makerspace, target=payment,
                     meta={"claim_id": claim.pk, "awaiting_confirmation": False})
    else:
        audit.record(actor, "payment.paid_claim_rejected", makerspace=payment.makerspace, target=payment,
                     meta={"claim_id": claim.pk})
    from apps.payments.notifications_l5 import notify_claim
    event = "paid_claim_confirmed" if confirmed else "paid_claim_rejected"
    transaction.on_commit(lambda: notify_claim(claim, event))
    return claim

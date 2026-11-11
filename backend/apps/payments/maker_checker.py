"""Maker-checker for offline settlements (owner decision 71: a per-space switch).

With the `billing.maker_checker` switch on, recording a cash/UPI/bank receipt does not mark
the charge paid. It writes a `SettlementConfirmation` awaiting a SECOND person who also
holds RECORD_PAYMENT authority for that charge; only their confirmation writes the
`ManualSettlement` and flips the charge, in one transaction. The maker can never confirm
their own proposal (409 `self_confirmation`, and a database check behind it).
"""

from django.utils.translation import gettext
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import APIException, NotFound

from apps.audit import services as audit
from apps.payments.models import Payment, SettlementConfirmation


class ConfirmationConflict(APIException):
    status_code = 409

    def __init__(self, detail, code):
        self.detail = {"detail": detail, "code": code}


def requires_confirmation(space):
    """Offline INCOME only (#128 C-5): refunds, expenses and payouts never wait for a checker."""
    from apps.makerspaces.platform import feature_enabled

    return feature_enabled(space, "billing.maker_checker")


def propose(locked_payments, actor, settlement, *, claim=None):
    """Proposals for LOCKED pending charges. The charges stay pending."""
    rows = []
    for payment in locked_payments:
        if SettlementConfirmation.objects.filter(payment=payment, status=SettlementConfirmation.Status.AWAITING).exists():
            raise ConfirmationConflict("A settlement for this charge is already awaiting confirmation.",
                                       "settlement_awaiting_confirmation")
        row = SettlementConfirmation.objects.create(
            payment=payment, method=settlement["method"], reference=settlement.get("reference", ""),
            received_at=settlement["received_at"], amount=payment.amount, currency=payment.currency,
            proposed_by=actor, claim=claim)
        audit.record(actor, "payment.settlement_awaiting_confirmation", makerspace=payment.makerspace,
                     target=payment, meta={"confirmation_id": row.pk, "method": row.method})
        from apps.payments.notifications_l5 import notify_confirmation
        transaction.on_commit(lambda row=row: notify_confirmation(row))
        rows.append(row)
    return rows


def _locked(actor, makerspace_id, confirmation_id):
    from rest_framework.exceptions import PermissionDenied
    from apps.accounts import rbac

    row = SettlementConfirmation.objects.filter(pk=confirmation_id, payment__makerspace_id=makerspace_id).first()
    if row is None:
        raise NotFound(gettext("Settlement confirmation not found."))
    payment = Payment.objects.select_for_update(of=("self",)).select_related("makerspace").get(pk=row.payment_id)
    from apps.payments.unit_payer_scope import payer_user_ids

    payers = payer_user_ids(actor, makerspace_id, rbac.Action.RECORD_PAYMENT)
    if payers is not None and payment.member_id not in payers:  # parity O-B3 (rule 261): out of unit scope
        raise NotFound(gettext("Payment not found."))
    row = SettlementConfirmation.objects.select_for_update().get(pk=row.pk)
    # The checker must hold RECORD_PAYMENT itself; domain authority is not enough here.
    if not rbac.scope_by_action(actor, rbac.Action.RECORD_PAYMENT, Payment.objects.filter(pk=payment.pk)).exists():
        raise PermissionDenied(gettext("Confirming a settlement needs record_payment."))
    if row.status != SettlementConfirmation.Status.AWAITING:
        raise ConfirmationConflict("This settlement has already been decided.", "settlement_decided")
    if row.proposed_by_id == actor.pk:
        raise ConfirmationConflict("A second person must confirm a settlement you recorded.", "self_confirmation")
    return payment, row


@transaction.atomic
def confirm(*, actor, makerspace_id, confirmation_id):
    from apps.payments.reconciliation import PaymentConflict, apply_reconciliation

    payment, row = _locked(actor, makerspace_id, confirmation_id)
    if payment.status != Payment.Status.PENDING:
        raise PaymentConflict([payment.pk])
    from apps.payments.settlement_supersede import keeping
    with keeping(claim_id=row.claim_id, confirmation_id=row.pk):
        receipt = apply_reconciliation(
            payment, actor, Payment.Status.PAID_OFFLINE,
            {"method": row.method, "reference": row.reference, "received_at": row.received_at},
            recorded_by=row.proposed_by)
    row.status, row.decided_by, row.decided_at, row.settlement = (
        SettlementConfirmation.Status.CONFIRMED, actor, timezone.now(), receipt)
    row.save()
    audit.record(actor, "payment.settlement_confirmed", makerspace=payment.makerspace, target=payment,
                 meta={"confirmation_id": row.pk, "settlement_id": receipt.pk})
    if row.claim_id:
        from apps.payments.offline_claims import finish_claim
        finish_claim(row.claim, actor, confirmed=True)
    return row


@transaction.atomic
def reject(*, actor, makerspace_id, confirmation_id, note=""):
    payment, row = _locked(actor, makerspace_id, confirmation_id)
    row.status, row.decided_by, row.decided_at = SettlementConfirmation.Status.REJECTED, actor, timezone.now()
    row.decision_note = (note or "").strip()[:500]
    row.save()
    audit.record(actor, "payment.settlement_rejected", makerspace=payment.makerspace, target=payment,
                 meta={"confirmation_id": row.pk})
    if row.claim_id:
        from apps.payments.offline_claims import finish_claim
        finish_claim(row.claim, actor, confirmed=False, note=row.decision_note)
    return row

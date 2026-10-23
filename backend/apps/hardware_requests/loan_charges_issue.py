"""Loan deposit: the issue gate and the post-issue raise.

Split out of `loan_payments.py` (still the public barrel). Every entry point swallows
payment failures, because a provider outage must never stop a handover.
"""

from decimal import Decimal

from apps.audit import services as audit
from apps.hardware_requests import notifications
from apps.hardware_requests.loan_charges_common import (
    ZERO,
    _get_or_create,
    _schedule_checkout,
    loans_enabled,
    logger,
)
from apps.hardware_requests.models import HardwareRequest
from apps.hardware_requests.workflow_errors import DepositRequired
from apps.payments.models import MakerspacePaymentSettings, Payment


def deposit_amount(request, settings_row):
    mode = settings_row.loan_deposit_mode
    if mode == MakerspacePaymentSettings.LoanDepositMode.FIXED:
        return Decimal(settings_row.loan_deposit_amount or 0)
    if mode == MakerspacePaymentSettings.LoanDepositMode.PER_PRODUCT:
        total = ZERO
        for item in request.items.select_related("product"):
            per_unit = item.product.deposit_amount
            if per_unit and item.accepted_quantity > 0:
                total += Decimal(per_unit) * item.accepted_quantity
        return total
    return ZERO


def require_deposit_settled(request, actor):
    """Refuse an issue only while a blocking deposit is unpaid. Failing open on any
    payment-system error is deliberate: a Stripe outage is not a reason to keep tools
    on the shelf, and the deposit is still raised post-commit by `raise_deposit`."""
    try:
        if request.status != HardwareRequest.Status.ACCEPTED:
            return None
        settings_row = MakerspacePaymentSettings.for_makerspace(request.makerspace)
        if not settings_row.loan_deposit_blocks_issue or not loans_enabled(request.makerspace):
            return None
        amount = deposit_amount(request, settings_row)
        if amount <= 0:
            return None
        payment = _deposit(request, actor, amount, settings_row.default_currency)
    except Exception:
        logger.exception("loan_deposit_gate_failed", extra={"request_id": request.pk})
        return None
    if payment.status == Payment.Status.PENDING:
        raise DepositRequired(payment)
    return payment


def raise_deposit(request_id, actor):
    """Post-commit: raise (or find) the deposit for a loan that was just issued."""
    try:
        request = HardwareRequest.objects.select_related("makerspace").get(pk=request_id)
        if request.status != HardwareRequest.Status.ISSUED:
            return None
        settings_row = MakerspacePaymentSettings.for_makerspace(request.makerspace)
        if not loans_enabled(request.makerspace):
            return None
        amount = deposit_amount(request, settings_row)
        if amount <= 0:
            return None
        return _deposit(request, actor, amount, settings_row.default_currency)
    except Exception:
        logger.exception("loan_deposit_raise_failed", extra={"request_id": request_id})
        return None


def _deposit(request, actor, amount, currency):
    payment, created = _get_or_create(
        request, Payment.SubjectType.LOAN_DEPOSIT, amount, currency,
        actor, f"Loan deposit - request #{request.pk}",
    )
    if created:
        audit.record(
            actor, "loan.deposit_raised", makerspace=request.makerspace, target=request,
            meta={"request_id": request.pk, "payment_id": payment.pk},
        )
        notifications.notify_loan_charge(request, "deposit_raised", payment)
    if payment.status == Payment.Status.PENDING:
        _schedule_checkout(payment)
    return payment

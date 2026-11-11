"""Loan charges at issue: the deposit gate, the deposit, and rental charged at checkout.

Split out of `loan_payments.py` (still the public barrel). Every entry point swallows
payment failures, because a provider outage must never stop a handover. Amounts come
from the pricing kernel (`apps.payments.pricing.quote`, lane L15), so the preview a
member saw and the charge raised are the same computation.

* Deposit: release-1 behaviour (fixed per loan, or per item) through the rate card;
  never discounted or waived. A deposit only ever BLOCKS a reviewed handover, and only
  when the space opted in; a direct or kiosk handout is never blocked (A10).
* Rental at checkout (A1): for the planned days to the due date, once per loan. Renewals
  are not charged in v1; an early return refunds nothing automatically.
"""

from apps.audit import services as audit
from apps.hardware_requests import notifications
from apps.hardware_requests.loan_charges_common import (
    _get_or_create,
    _schedule_checkout,
    fee_exempt,
    loans_enabled,
    logger,
)
from apps.hardware_requests.models import HardwareRequest
from apps.hardware_requests.workflow_errors import DepositRequired
from apps.payments.models import MakerspacePaymentSettings, Payment


def deposit_quote(request):
    from apps.payments.pricing import quote

    return quote(request.makerspace, "loans", request, params={"components": ("deposit",)}, discounts=False)


def deposit_amount(request, settings_row=None):
    """Kept for callers of the barrel: the deposit this loan owes now."""
    return deposit_quote(request).total


def require_deposit_settled(request, actor):
    """Refuse an issue only while a blocking deposit is unpaid. Failing open on any
    payment-system error is deliberate: a Stripe outage is not a reason to keep tools
    on the shelf, and the deposit is still raised post-commit by `raise_deposit`."""
    try:
        if request.status != HardwareRequest.Status.ACCEPTED:
            return None
        settings_row = MakerspacePaymentSettings.for_makerspace(request.makerspace)
        if (not settings_row.loan_deposit_blocks_issue or not loans_enabled(request.makerspace)
                or fee_exempt(request)):
            return None
        priced = deposit_quote(request)
        if priced.total <= 0:
            return None
        payment = _deposit(request, actor, priced)
    except Exception:
        logger.exception("loan_deposit_gate_failed", extra={"request_id": request.pk})
        return None
    if payment.status == Payment.Status.PENDING:
        raise DepositRequired(payment)
    return payment


def on_request_issued(request_id, actor):
    """Post-commit, for EVERY issue path (reviewed, direct, kiosk, self-checkout)."""
    deposit = raise_deposit(request_id, actor)
    raise_rental_at_checkout(request_id, actor)
    return deposit


def raise_deposit(request_id, actor):
    """Post-commit: raise (or find) the deposit for a loan that was just issued."""
    try:
        request = HardwareRequest.objects.select_related("makerspace").get(pk=request_id)
        if (request.status != HardwareRequest.Status.ISSUED or not loans_enabled(request.makerspace)
                or fee_exempt(request)):
            return None
        priced = deposit_quote(request)
        if priced.total <= 0:
            return None
        return _deposit(request, actor, priced)
    except Exception:
        logger.exception("loan_deposit_raise_failed", extra={"request_id": request_id})
        return None


def _deposit(request, actor, priced):
    payment, created = _get_or_create(
        request, Payment.SubjectType.LOAN_DEPOSIT, priced, actor, f"Loan deposit - request #{request.pk}",
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


def raise_rental_at_checkout(request_id, actor):
    from apps.hardware_requests.loan_charges_rental import raise_rental

    try:
        request = HardwareRequest.objects.select_related("makerspace").get(pk=request_id)
        if request.status != HardwareRequest.Status.ISSUED:
            return None
        return raise_rental(request, actor, at="checkout")
    except Exception:
        logger.exception("loan_rental_raise_failed", extra={"request_id": request_id})
        return None

"""Shared helpers for loan charges: tracking switch, idempotent raise, optional rail.

Split out of `loan_payments.py` (still the public barrel). Amounts are `Decimal` major
units, like every Payment row. Never floats. Every amount is a frozen `Quote` from the
pricing kernel (lane L15); the Payment carries it as `pricing_snapshot`.
"""

import logging
from decimal import Decimal

from django.db import IntegrityError, transaction

from apps.hardware_requests.models import HardwareRequest
from apps.payments.availability import charge_tracking_enabled, online_payments_enabled
from apps.payments.models import Payment
from apps.payments.services import create_checkout, create_payment

logger = logging.getLogger("apps.hardware_requests.loan_payments")

CLOSED_STATUSES = frozenset(
    {HardwareRequest.Status.RETURNED, HardwareRequest.Status.CLOSED_WITH_ISSUE}
)
ZERO = Decimal("0.00")


def loans_enabled(makerspace):
    """Whether loan deposits and late fees are RECORDED for this space.

    Tracking, not the online rail. `loan_deposit_blocks_issue` reads this, so keying it
    off gateway credentials would have made that setting silently mean nothing in a
    cash-only space: staff could switch "a deposit blocks issue" on and it would never
    block, because no deposit was ever raised to be unpaid. The rail is applied
    separately in `_schedule_checkout`.
    """
    return charge_tracking_enabled(makerspace, "loans")


def fee_exempt(request):
    """Decision 159(2): an account-less walk-in (or the anonymous requester) is never charged loan fees.

    Deposit, rental and late fee are all skipped, so no debt is recorded for someone who holds no
    account to pay it from; spaces that want to charge require accounts. Damage and loss go
    through staff accountability decisions, which stay available. Converting the walk-in to a
    full account (`is_walk_in` False) makes later loans chargeable as usual.
    """
    from apps.accounts.principal_guards import is_anonymous_requester

    requester = request.requester
    return bool(requester is not None and (requester.is_walk_in or is_anonymous_requester(requester)))


def _existing(request, subject_type, subject_id=None):
    return Payment.objects.filter(
        makerspace=request.makerspace, subject_type=subject_type,
        subject_id=request.pk if subject_id is None else subject_id,
    ).first()


def _get_or_create(request, subject_type, priced, actor, label, *, subject_id=None):
    """The one charge for (request or accountability row, subject); `priced` is its Quote."""
    existing = _existing(request, subject_type, subject_id)
    if existing is not None:
        return existing, False
    from apps.hardware_requests.guest_liability import liable_member
    # Decision 223 (f): a sponsored guest's charge goes to the sponsor when the space says so.
    billed = liable_member(request)
    try:
        with transaction.atomic():
            payment = create_payment(
                makerspace=request.makerspace,
                subject_type=subject_type,
                subject_id=request.pk if subject_id is None else subject_id,
                member=billed,
                amount=priced.total,
                currency=priced.currency,
                created_by=actor or request.requester,
                subject_label=label,
                pricing_snapshot=priced.to_snapshot(),
            )
            if getattr(billed, "pk", None) != request.requester_id:
                from apps.audit import services as audit
                audit.record(actor or request.requester, "membership.guest_pass_charge_redirected",
                             makerspace=request.makerspace, target=request,
                             meta={"request_id": request.pk, "payment_id": payment.pk, "guest_id": request.requester_id,
                                   "sponsor_id": billed.pk, "subject": str(subject_type)})
            return payment, True
    except IntegrityError:
        return _existing(request, subject_type, subject_id), False


def _schedule_checkout(payment):
    # The debt is already recorded by the caller; a rail is optional on top of it.
    if not online_payments_enabled(payment.makerspace, "loans"):
        return

    def create_safely():
        try:
            create_checkout(payment)
        except Exception:
            logger.exception("loan_checkout_schedule_failed", extra={"payment_id": payment.pk})

    transaction.on_commit(create_safely)

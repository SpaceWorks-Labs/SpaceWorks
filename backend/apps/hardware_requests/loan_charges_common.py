"""Shared helpers for loan charges: tracking switch, idempotent raise, optional rail.

Split out of `loan_payments.py` (still the public barrel). Amounts are `Decimal` major
units, like every Payment row. Never floats.
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


def _existing(request, subject_type):
    return Payment.objects.filter(
        makerspace=request.makerspace, subject_type=subject_type, subject_id=request.pk
    ).first()


def _get_or_create(request, subject_type, amount, currency, actor, label):
    existing = _existing(request, subject_type)
    if existing is not None:
        return existing, False
    try:
        with transaction.atomic():
            return create_payment(
                makerspace=request.makerspace,
                subject_type=subject_type,
                subject_id=request.pk,
                member=request.requester,
                amount=amount.quantize(Decimal("0.01")),
                currency=currency,
                created_by=actor or request.requester,
                subject_label=label,
            ), True
    except IntegrityError:
        return _existing(request, subject_type), False


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

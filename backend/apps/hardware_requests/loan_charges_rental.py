"""Loan rental: one `loan_rental` charge per loan, at checkout or at return (A1).

The space's `rental_timing` is read when the loan is ISSUED, and that choice sticks to
the loan: a change applies only to loans issued after it.

* `at_checkout` -- raised post-commit at issue, for the planned days (issue to due date).
* `at_return` -- the issue records `loan.rental_deferred` on the loan's audit trail (the
  append-only record of which timing the loan was issued under), and the close raises
  the rental for the actual days (the ceiling of the time issued).

The cap applies per unit of each item line in both modes. The late fee is separate and
still applies on top. Renewals are not charged in v1, and an early return refunds
nothing automatically -- the member may ask for a refund, staff decide.
"""

from django.utils import timezone

from apps.audit import services as audit
from apps.hardware_requests import notifications
from apps.hardware_requests.loan_charges_common import (
    _existing,
    _get_or_create,
    _schedule_checkout,
    fee_exempt,
    loans_enabled,
)
from apps.payments.models import Payment

DEFERRED = "loan.rental_deferred"


def _was_deferred(request):
    from apps.audit.models import AuditLog

    return AuditLog.objects.filter(makerspace_id=request.makerspace_id, action=DEFERRED,
                                   target_type="hardware_requests.hardwarerequest",
                                   target_id=str(request.pk)).exists()


def raise_rental(request, actor, *, at, now=None):
    from apps.payments.models_pricing import PricingDefault
    from apps.payments.pricing import quote
    from apps.payments.pricing.build_loans import days_between
    from apps.payments.pricing.charging import record_free
    from apps.payments.pricing.resolver import rate_card

    if not loans_enabled(request.makerspace) or fee_exempt(request):
        return None
    card = rate_card(request.makerspace, "loans")
    if not card.enabled or _existing(request, Payment.SubjectType.LOAN_RENTAL) is not None:
        return None
    if at == "checkout":
        if card.rental_timing == PricingDefault.RentalTiming.AT_RETURN:
            audit.record(actor, "loan.rental_deferred", makerspace=request.makerspace, target=request,
                         meta={"request_id": request.pk, "rental_timing": card.rental_timing})
            return None
        days = days_between(request.issued_at, request.return_due_at)
    else:
        if not _was_deferred(request):
            return None
        days = days_between(request.issued_at, now or request.closed_at or timezone.now())
    priced = quote(request.makerspace, "loans", request, member=request.requester,
                   params={"components": ("rental",), "days": days}, card=card)
    if priced.total <= 0:
        if priced.lines:
            record_free(priced, actor=actor, makerspace=request.makerspace, target=request,
                        subject_type=Payment.SubjectType.LOAN_RENTAL, subject_id=request.pk)
        return None
    payment, created = _get_or_create(request, Payment.SubjectType.LOAN_RENTAL, priced, actor,
                                      f"Loan rental - request #{request.pk}")
    if created:
        audit.record(actor, "loan.rental_raised", makerspace=request.makerspace, target=request, meta={
            "request_id": request.pk, "payment_id": payment.pk, "days": days, "timing": at,
            "discount_id": (priced.discount or {}).get("id"), "discount_saving": (priced.discount or {}).get("saving"),
        })
        notifications.notify_loan_charge(request, "rental_raised", payment)
    if payment.status == Payment.Status.PENDING:
        _schedule_checkout(payment)
    return payment


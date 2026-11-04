"""Job-flow money rules on top of L15's machine charge seam (#142 OQ-3/OQ-4/OQ-8).

Every amount comes from L15 (`service_payments.service_quote` / `pricing.quote`); this
module only decides WHICH price applies:

* completion (pay at completion): the actual usage, CAPPED at the quote the member
  approved -- when the actual costs more, the frozen quote is charged instead;
* prepay: the frozen quote is raised as a PENDING charge when the member approves; the
  job joins the queue once staff or the rail settle it, and is never charged again;
* a re-run of a prepaid job (a space-fault re-queue inherits `prepay`) is never charged again;
* a failed job: L15's `create_for_failed_request` with the per-type member-fault choice.

Money never moves here: a charge is a pending `Payment` staff or the member settle.
"""

import logging

from django.db import transaction

from apps.payments.models import Payment

logger = logging.getLogger(__name__)
SUBJECT = Payment.SubjectType.MACHINE_SERVICE_REQUEST


def payment_for(job):
    return Payment.objects.filter(makerspace_id=job.makerspace_id, subject_type=SUBJECT, subject_id=job.pk).first()


def prepaid_payment(job):
    """A prepaid job (or its re-run, which inherits `prepay`) is paid by the original's charge."""
    return payment_for(job.reprint_of or job)


def frozen(job):
    from apps.payments.pricing.quotes import FrozenQuote
    return FrozenQuote(job.quote_snapshot) if job.quote_snapshot else None


def _raise_frozen(job, actor, quote):
    from apps.payments.availability import charge_tracking_enabled
    from apps.payments.pricing.charging import raise_priced
    from apps.payments.services import create_payment
    try:
        with transaction.atomic():
            if not charge_tracking_enabled(job.makerspace, "machines"):
                return None
            existing = payment_for(job)
            if existing is not None:
                return existing
            payment = raise_priced(quote, makerspace=job.makerspace, subject_type=SUBJECT, subject_id=job.pk,
                                   member=job.member or job.requester,
                                   created_by=actor or job.accepted_by or job.handled_by, target=job,
                                   create=create_payment)
    except Exception:
        logger.exception("machine_job_charge_not_recorded", extra={"service_request_id": job.pk})
        return None
    _offer_checkout(job, payment)
    return payment


def _offer_checkout(job, payment):
    """Same as the L15 seam: an online checkout only where the rail is live; never blocks."""
    from apps.payments.availability import online_payments_enabled
    from apps.payments.services import create_checkout
    if payment is not None and online_payments_enabled(job.makerspace, "machines"):
        try:
            create_checkout(payment)
        except Exception:
            logger.warning("machine_job_checkout_not_created", extra={"service_request_id": job.pk})


def raise_prepay(job, actor):
    """The member approved a prepaid quote: raise exactly the quoted amount, pending."""
    quote = frozen(job)
    return _raise_frozen(job, actor, quote) if quote is not None else None


def charge_completed(job, actor):
    from apps.machines import service_payments
    if job.prepay:
        # #171 (3): a prepaid job that came in cheaper than its quote opens a difference case.
        from apps.machines.job_refunds import open_difference
        open_difference(job, actor)
        return prepaid_payment(job)
    quote = frozen(job)
    if quote is not None:
        try:
            actual = service_payments.service_quote(job)
        except Exception:
            logger.exception("machine_job_actual_quote_failed", extra={"service_request_id": job.pk})
            actual = None
        if actual is None or actual.total > quote.total:
            return _raise_frozen(job, actor, quote)
    return service_payments.create_for_completed_request(job, actor)


def charge_failed(job, actor, failure_charge):
    from apps.machines import service_payments
    if job.prepay:
        return prepaid_payment(job)
    return service_payments.create_for_failed_request(job, actor, failure_charge=failure_charge)


def settled(payment):
    return payment is not None and payment.status in (Payment.Status.PAID_ONLINE, Payment.Status.PAID_OFFLINE,
                                                      Payment.Status.WAIVED)


def open_refund_due(job, actor):
    """A prepaid job the space will not run: open a staff-approved refund case (#59)."""
    payment = payment_for(job)
    if payment is None or not settled(payment) or payment.status == Payment.Status.WAIVED:
        return None
    try:
        from apps.payments.models import RefundCase
        from apps.payments.services_refund_cases import open_due_case
        return open_due_case(payment, reason_code=RefundCase.ReasonCode.STAFF_CANCELLED, actor=actor)
    except Exception:
        logger.exception("machine_job_refund_case_not_opened", extra={"service_request_id": job.pk})
        return None

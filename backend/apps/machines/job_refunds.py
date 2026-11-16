"""Prepaid-job refund cases opened automatically, decided by staff (#171 (2) and (3)).

Always on wherever machine charging is on (`charge_tracking_enabled(space, "machines")`);
`charges.price_drop_refunds` does not gate them. Nothing here moves money: each case
waits in the refund queue for a staff decision (#59).

* (2) The member cancels a prepaid job before it starts. A SETTLED charge gets a
  `job_cancelled` case for everything left to refund on it; the job's Machine Manager
  decides it like a staff cancellation (`staff_cancelled`, which stays as it was). A
  charge still PENDING is voided instead -- nothing will be made, so nothing is owed.
* (3) A prepaid job comes in cheaper than its quote. At completion the actual usage is
  priced exactly as an unpaid job would be (`service_payments.service_quote`), and a
  member-fault failure under the space's failure charge; when that is below the quote --
  or below a price it was already brought down to by a price drop -- a `quote_difference`
  case opens for the difference, decided by the Space Manager or a finance admin like a
  price drop. A re-run is paid by its original's charge and compared against it.

A failure never blocks the job flow: errors are logged, the job's transition stands.
"""

import logging

from django.db import transaction

from apps.payments.models import Payment, RefundCase

logger = logging.getLogger(__name__)
SETTLED = (Payment.Status.PAID_ONLINE, Payment.Status.PAID_OFFLINE)


def _tracking(job):
    from apps.payments.availability import charge_tracking_enabled
    return charge_tracking_enabled(job.makerspace, "machines")


def _item(payment):
    return f"machine_job:{payment.subject_id}"


def on_cancel_before_start(job, actor, *, by_owner):
    """A prepaid job cancelled before it ran: void its pending charge, or open its case."""
    from apps.machines.job_charges import payment_for, prepaid_payment
    try:
        with transaction.atomic():
            payment = prepaid_payment(job)
            if payment is None:
                return None
            if payment.status == Payment.Status.PENDING:
                own = payment_for(job)
                if own is not None and own.pk == payment.pk:
                    from apps.payments.reconciliation import cancel_pending
                    cancel_pending(makerspace=job.makerspace, subject_type=payment.subject_type,
                                   subject_id=payment.subject_id, actor=actor)
                return None
            if payment.status not in SETTLED:
                return None
            if not by_owner:
                from apps.payments.services_refund_cases import open_due_case
                return open_due_case(payment, reason_code=RefundCase.ReasonCode.STAFF_CANCELLED, actor=actor)
            if not _tracking(job):
                return None
            from apps.payments.refund_policy import refundable_balance
            from apps.payments.services_refund_partial import add_due_share
            return add_due_share(payment, amount=refundable_balance(payment), actor=actor,
                                 reason_code=RefundCase.ReasonCode.JOB_CANCELLED,
                                 snapshot={"source": "job_cancelled", "item": _item(payment),
                                           "service_request_id": job.pk})
    except Exception:
        logger.exception("machine_job_cancel_refund_not_opened", extra={"service_request_id": job.pk})
        return None


def open_difference(job, actor, *, outcome="completed", failure_charge=None):
    """(3): the actual price of a prepaid job, against what its charge paid for."""
    from apps.machines.job_charges import prepaid_payment
    try:
        with transaction.atomic():
            payment = prepaid_payment(job)
            if payment is None or payment.status not in SETTLED or not _tracking(job):
                return None
            from apps.machines.service_payments import service_quote
            from apps.payments.price_drop.hook import open_share
            from apps.payments.price_drop.shares import Affected, by_total, frozen_total
            payment = Payment.objects.prefetch_related("refund_cases").get(pk=payment.pk)
            actual = service_quote(job, outcome=outcome, failure_charge=failure_charge).total
            result = by_total(payment, _item(payment), before=frozen_total(payment), after=actual)
            if result is None:
                return None
            baseline, owed = result
            affected = Affected(area="machines", item_type="machine_job", item_id=payment.subject_id,
                                label=f"Machine job #{job.pk}", payment=payment, before=baseline, after=actual,
                                difference=owed, facts={"service_request_id": job.pk, "outcome": outcome})
            return open_share(affected, actor=actor, reason_code=RefundCase.ReasonCode.QUOTE_DIFFERENCE,
                              source="quote_difference")
    except Exception:
        logger.exception("machine_job_difference_case_not_opened", extra={"service_request_id": job.pk})
        return None

"""Machine-service charging boundary; payment failures never affect fulfilment.

The amount comes from the pricing kernel (lane L15): time + material + per job, each
resolved per component (pool / machine override, the type's pricing row, the space
default), with the billing increment and minimum, and the member's best automatic
discount. The quote is frozen on the charge. A job priced at 0 raises nothing.

A failed job is free by default (A11). `create_for_failed_request` charges it under the
space's (or the caller's) failure choice -- none, material only, or full -- and is the
seam lane L12's job flow calls with the per-type, per-fault choice (#142 OQ-8). A job
cancelled while running is never charged (#58/#61): nothing here is called for it.
"""

import logging
from decimal import Decimal, InvalidOperation

from django.db import transaction

from apps.payments.availability import charge_tracking_enabled, online_payments_enabled
from apps.payments.models import Payment
from apps.payments.services import create_checkout, create_payment

logger = logging.getLogger(__name__)


def effective_quantity(service_request, machine_type):
    config = machine_type.capability_config or {}
    if config.get("metering_unit") == "minutes":
        return _decimal(service_request.actual_minutes)
    quantity = service_request.actual_consumed_quantity
    if quantity is not None:
        return _decimal(quantity)
    return _decimal(service_request.actual_consumed_grams)


def service_quote(service_request, *, outcome="completed", failure_charge=None, member=None):
    from apps.payments.pricing import quote

    return quote(service_request.makerspace, "machines", service_request,
                 member=member or service_request.member or service_request.requester,
                 params={"outcome": outcome, "failure_charge": failure_charge})


def create_for_completed_request(service_request, actor):
    return _raise(service_request, actor, outcome="completed")


def create_for_failed_request(service_request, actor, *, failure_charge=None):
    """L12 seam: charge a failed job under `failure_charge` (default: the space's choice)."""
    return _raise(service_request, actor, outcome="failed", failure_charge=failure_charge)


def _raise(service_request, actor, *, outcome, failure_charge=None):
    from apps.payments.pricing.charging import raise_priced

    try:
        with transaction.atomic():
            if service_request.assigned_machine_id is None:
                return None
            if not charge_tracking_enabled(service_request.makerspace, "machines"):
                return None
            existing = Payment.objects.filter(
                makerspace=service_request.makerspace, subject_type=Payment.SubjectType.MACHINE_SERVICE_REQUEST,
                subject_id=service_request.pk).first()
            if existing is not None:
                return existing
            priced = service_quote(service_request, outcome=outcome, failure_charge=failure_charge)
            payment = raise_priced(
                priced, makerspace=service_request.makerspace,
                subject_type=Payment.SubjectType.MACHINE_SERVICE_REQUEST, subject_id=service_request.pk,
                member=service_request.member or service_request.requester,
                # A device-applied completion has no human actor (a device is never an
                # actor), but the ledger needs a real User: attribute the charge to the
                # staff member who accepted the job into the queue.
                created_by=actor or service_request.accepted_by or service_request.handled_by,
                target=service_request, create=create_payment,
                # NO subject_label. `title` is free text a public member types, so it can
                # contain their name, email or phone -- and a snapshot outlives the
                # `machine_service` purge that exists to destroy exactly that. Leaving it
                # blank keeps the live lookup (which still shows the title while the request
                # exists) and degrades to the generic display once the request is gone.
            )
    except Exception:
        # Fulfilment must not fail on a charge error, but a debt that silently vanishes
        # is lost money: always leave a trace.
        logger.exception(
            "machine_service_charge_not_recorded", extra={"service_request_id": service_request.pk}
        )
        return None
    if payment is not None and online_payments_enabled(service_request.makerspace, "machines"):
        try:
            create_checkout(payment)
        except Exception:
            pass
    return payment


def _decimal(value):
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal("0")
    return parsed if parsed.is_finite() else Decimal("0")

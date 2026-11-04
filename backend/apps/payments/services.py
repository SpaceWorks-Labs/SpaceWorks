"""Raising a payment: the charge itself, independent of any online rail.

The rail lives in `services_checkout`; this module re-exports it, and the webhook
handlers, so `from apps.payments.services import X` keeps resolving for every caller.
"""

from apps.accounts.account_kind_guards import require_member_account

import logging

from django.db import transaction

from apps.audit import services as audit
# Re-exported, not used here: tests and callers reach it through this barrel.
from apps.makerspaces.platform import member_payment_return_url  # noqa: F401
from apps.payments.models import Payment
from apps.payments.resolution import resolve_payment_source

# Re-export barrel: these moved out at the 300-line ceiling.
from apps.payments.services_checkout import (  # noqa: F401
    PaymentRailConflict,
    _application_fee_amount,
    _ConnectAccountCannotCharge,
    create_checkout,
    create_checkout_url,
)
from apps.payments.services_webhooks import (  # noqa: F401
    apply_connect_webhook_event,
    apply_razorpay_webhook_event,
    apply_webhook_event,
)

logger = logging.getLogger(__name__)


@transaction.atomic
def create_payment(
    *, makerspace, subject_type, subject_id, member, amount, currency, created_by,
    via_makerspace=None, subject_label="", due_at=None, pricing_snapshot=None,
):
    # A missing source is NOT fatal any more. Recording what a member owes is separate
    # from being able to collect it online: a space that takes cash still needs the debt
    # on the books, visible in the member area and settleable by staff. The row is stamped
    # `unclaimed` and the first checkout that reaches a provider claims it.
    require_member_account(member)
    # Tax is frozen once, here, the single seam every domain raises charges through. With
    # `billing.tax` off this returns the amount unchanged and no snapshot (release 1).
    from apps.payments.tax.snapshot import freeze_for_charge
    amount, tax_snapshot = freeze_for_charge(makerspace, amount, currency, member)
    source = resolve_payment_source(makerspace)
    if source is None:
        vendor = Payment.Provider.UNCLAIMED
        provider = Payment.StripeProvider.RAW
        connected_account_id = None
        fee_amount = 0
    else:
        vendor = source.vendor
        provider = source.provider
        connected_account_id = source.connected_account_id
        fee_amount = _application_fee_amount(amount, source.application_fee_bps, currency)
    from apps.payments.due_dates import default_due_at
    payment = Payment.objects.create(
        makerspace=makerspace,
        subject_type=subject_type,
        subject_id=subject_id,
        member=member,
        via_makerspace=via_makerspace,
        subject_label=(subject_label or "")[:255],
        amount=amount,
        currency=currency.lower(),
        created_by=created_by,
        due_at=due_at if due_at is not None else default_due_at(makerspace, actor=created_by),
        # Stamped at creation from whatever resolved NOW, and immutable thereafter: a
        # space that switches vendor must still settle and expire the charges it raised
        # under the old one, and moving a row between vendors would point it at a
        # merchant account that never took the money.
        provider=vendor,
        stripe_provider=provider,
        stripe_connected_account_id=connected_account_id,
        stripe_application_fee_amount=fee_amount,
        tax_snapshot=tax_snapshot,
        # Lane L15: the frozen net quote this amount came from (insert-only).
        pricing_snapshot=pricing_snapshot or {},
    )
    # Raising a charge is when a member incurs a debt; the log previously recorded
    # only its settlement.
    audit.record(
        created_by,
        "payment.created",
        makerspace=makerspace,
        target=payment,
        meta={
            "payment_id": payment.pk,
            "subject_type": subject_type,
            "subject_id": subject_id,
            "amount": str(amount),
            "currency": payment.currency,
            "via_makerspace_id": via_makerspace.pk if via_makerspace else None,
            # Lane L15: the automatic discount this raise applied, if any.
            "discount_id": _discount(pricing_snapshot).get("id"),
            "discount_saving": _discount(pricing_snapshot).get("saving"),
        },
    )
    from apps.payments.notifications import notify_payment
    notify_payment(payment, "charge_raised")
    # An optional document must never poison the required debt transaction.
    try:
        with transaction.atomic():
            from apps.payments.documents import issue_bill
            issue_bill(payment, actor=created_by)
    except Exception as exc:
        logger.error("payment_bill_issue_failed", extra={
            "payment_id": payment.pk, "failure_type": type(exc).__name__,
        })
    return payment


def _discount(snapshot):
    """Lane L15: the discount a raise applied, named in its audit entry."""
    return (snapshot or {}).get("discount") or {}


from apps.payments.reconciliation import mark_offline, waive  # noqa: E402,F401

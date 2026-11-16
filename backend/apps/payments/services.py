"""Raising a payment: the charge itself, independent of any online rail.

The rail lives in `services_checkout`; this module re-exports it, and the webhook
handlers, so `from apps.payments.services import X` keeps resolving for every caller.
"""

from apps.accounts.account_kind_guards import require_member_account

import logging

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from apps.audit import services as audit
# Re-exported, not used here: tests and callers reach it through this barrel.
from apps.makerspaces.platform import member_payment_return_url  # noqa: F401
from apps.payments.models import Payment
from apps.payments.resolution import resolve_payment_source

# Re-export barrel: these moved out at the 300-line ceiling.
from apps.payments.services_checkout import (  # noqa: F401
    PaymentRailConflict,
    PaymentSettlementPending,
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
    via_makerspace=None, subject_label="", due_at=None, pricing_snapshot=None, frozen_tax=None,
):
    # A missing source is NOT fatal any more. Recording what a member owes is separate
    # from being able to collect it online: a space that takes cash still needs the debt
    # on the books, visible in the member area and settleable by staff. The row is stamped
    # `unclaimed` and the first checkout that reaches a provider claims it.
    # Lanes L18 and L22: a guest's donation or shop order and a sponsor organisation's payment belong to no account.
    if member is not None or subject_type not in Payment.ACCOUNTLESS_SUBJECT_TYPES:
        require_member_account(member)
    # Tax is frozen once, here, the single seam every domain raises charges through. With
    # `billing.tax` off this returns the amount unchanged and no snapshot (release 1).
    # Lane L22: a shop order with per-product tax classes hands in its own frozen
    # `(amount, snapshot)`, built from the same engine line by line (`shop/tax_lines.py`).
    # A gift (lane L18) is never a taxable supply.
    from apps.payments.tax.snapshot import freeze_for_charge
    if frozen_tax is None:
        # Payments audit 0.12.0 (B-2): the debt is stored in what the provider can capture.
        # A JPY 1500.50 row was charged 1501 and receipted 1500.50; the tax engine's own
        # quantum (ISO exponent, capped at the column's 2 places) is the one rounding rule.
        from apps.payments.tax.engine import q
        amount = q(amount, currency)
    if frozen_tax is not None:
        amount, tax_snapshot = frozen_tax
    elif subject_type in Payment.UNTAXED_SUBJECT_TYPES:
        tax_snapshot = None
    else:
        amount, tax_snapshot = freeze_for_charge(makerspace, amount, currency, member)
        from apps.payments.tax.plan_sac import with_plan_sac  # parity O-B3: the plan's own SAC, frozen here
        tax_snapshot = with_plan_sac(makerspace, subject_type, subject_id, tax_snapshot)
    # `payments` is opt-in and buys the online rail ALONE: a charge is stamped with a vendor only while the
    # rail is genuinely on for its domain (module, master switch, domain feature AND credentials). Saved
    # credentials under an uninstalled module or a switched-off domain stamp nothing, so the debt is raised
    # `unclaimed` and the first checkout that reaches a provider claims it once. Existing charges keep their
    # stamp and the webhook still settles them: this decides only how a NEW row is born.
    from apps.payments.availability import SUBJECT_DOMAINS, online_payments_enabled
    domain = SUBJECT_DOMAINS.get(subject_type)
    rail_on = domain is not None and online_payments_enabled(makerspace, domain)
    source = resolve_payment_source(makerspace) if rail_on else None
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
    try:
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
    except ValidationError as exc:
        # Payments audit 0.12.0 (B-3): `full_clean` reports an already-raised charge for
        # this subject as a ValidationError, but every seam's replay/race recovery catches
        # IntegrityError -- the same duplicate then answered 500 instead of the existing charge.
        if Payment.objects.filter(makerspace=makerspace, subject_type=subject_type, subject_id=subject_id).exists():
            raise IntegrityError("payment_one_per_subject") from exc
        raise
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

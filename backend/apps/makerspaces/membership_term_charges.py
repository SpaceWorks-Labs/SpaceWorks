"""#184: a term staff open from the console charges its frozen price like every other seam.

Record first, rail second. With membership charges off (`charges.enabled` /
`charges.membership`) the term is free and nothing is recorded. With them on, the term's
frozen price becomes a pending `membership_term_start` charge on the member (subject = the
term, one row per term by the Payment table's subject constraint); staff mark it paid with a
receipt, or the member pays online when the membership rail is on. A failure to RECORD
propagates: both callers open the term in the same transaction, so the term rolls back
rather than opening with its debt silently dropped (debts are never lost). Only the
optional online rail is best-effort.
"""
import logging

from django.db import IntegrityError, transaction

from apps.audit import services as audit

logger = logging.getLogger(__name__)


def raise_term_start(actor, term):
    from apps.payments.availability import charge_tracking_enabled, online_payments_enabled
    from apps.payments.models import Payment
    from apps.payments.services import create_payment

    membership = term.membership
    space = membership.makerspace
    if term.price is None or term.price <= 0 or not charge_tracking_enabled(space, "membership"):
        return None
    lookup = dict(makerspace=space, subject_type=Payment.SubjectType.MEMBERSHIP_TERM_START, subject_id=term.pk)
    try:
        with transaction.atomic():
            if Payment.objects.filter(**lookup).exists():
                raise IntegrityError("term charge already recorded")
            # Decision 223 (k): approved volunteer hours reduce this charge as a recorded, audited credit.
            from apps.makerspaces.volunteer_credit import reduce_charge, stamp_applied
            currency = term.currency or term.plan.currency
            days = (term.ends_at - term.starts_at).days if term.ends_at else 365
            amount, used = reduce_charge(space, membership.user, term.price, currency, term_days=days or 1)
            if amount <= 0:
                stamp_applied(actor, space, used, None)
                # Same record as a covered renewal: which term the consumed credits paid for.
                audit.record(actor, "membership.term_charge_raised", makerspace=space, target=term,
                             meta={"membership_id": membership.pk, "term_id": term.pk, "payment_id": None,
                                   "covered_by_credit": True})
                return None
            payment = create_payment(**lookup, member=membership.user, amount=amount,
                                     currency=currency, created_by=actor,
                                     subject_label=f"Membership: {term.plan.name}", due_at=term.starts_at)
            stamp_applied(actor, space, used, payment)
    except IntegrityError:
        return Payment.objects.filter(**lookup).first()
    audit.record(actor, "membership.term_charge_raised", makerspace=space, target=term,
                 meta={"membership_id": membership.pk, "term_id": term.pk, "payment_id": payment.pk})
    try:
        if online_payments_enabled(space, "membership"):
            from apps.makerspaces.membership_payments import _schedule_checkout
            _schedule_checkout(payment)
    except Exception:  # noqa: BLE001 - the recorded debt stands; only the rail failed
        logger.warning("membership_term_checkout_schedule_failed", extra={"payment_id": payment.pk})
    return payment

"""#184: a term staff open from the console charges its frozen price like every other seam.

Record first, rail second. With membership charges off (`charges.enabled` /
`charges.membership`) the term is free and nothing is recorded. With them on, the term's
frozen price becomes a pending `membership_term_start` charge on the member (subject = the
term, one row per term by the Payment table's subject constraint); staff mark it paid with a
receipt, or the member pays online when the membership rail is on. A failure to record
never undoes the term (the debt is a consequence, not a precondition), and is logged.
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
            payment = create_payment(**lookup, member=membership.user, amount=term.price,
                                     currency=term.currency or term.plan.currency, created_by=actor,
                                     subject_label=f"Membership: {term.plan.name}", due_at=term.starts_at)
    except IntegrityError:
        return Payment.objects.filter(**lookup).first()
    except Exception:  # noqa: BLE001 - money never blocks the membership workflow
        logger.warning("membership_term_charge_failed", extra={"term_id": term.pk})
        return None
    audit.record(actor, "membership.term_charge_raised", makerspace=space, target=term,
                 meta={"membership_id": membership.pk, "term_id": term.pk, "payment_id": payment.pk})
    if online_payments_enabled(space, "membership"):
        from apps.makerspaces.membership_payments import _schedule_checkout
        _schedule_checkout(payment)
    return payment

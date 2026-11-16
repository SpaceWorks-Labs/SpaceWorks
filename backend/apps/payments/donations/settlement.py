"""After a gift's or sponsor's charge settles (the one settlement seam, `admission_settlement`).

Runs after the payment lock is released (same reason as admissions and ticket orders): the
gift is marked received, its 80G receipt frozen when one was asked for, and the giver thanked
with the receipt. A failure here never rolls back money received; staff can re-send.
"""

import logging

from django.db import transaction
from django.utils import timezone

from apps.audit import services as audit

logger = logging.getLogger(__name__)
SETTLED = ("paid_online", "paid_offline")


def after_settlement(payment):
    payment_id, subject_type, subject_id, status = payment.pk, payment.subject_type, payment.subject_id, payment.status

    def resume():
        try:
            if subject_type == "donation":
                mark_gift(subject_id, status)
            else:
                mark_sponsorship(payment_id, subject_id, status)
        except Exception as exc:
            logger.warning("donation_settlement_failed", extra={
                "payment_id": payment_id, "failure_type": type(exc).__name__})

    transaction.on_commit(resume)


def mark_gift(donation_id, status):
    from .models import Donation
    from .notices import notify_receipt
    from .tax_receipts import freeze

    with transaction.atomic():
        donation = Donation.objects.select_for_update().select_related("makerspace").filter(pk=donation_id).first()
        if donation is None or donation.status != Donation.Status.PENDING:
            return donation
        if status in SETTLED:
            donation.status, donation.paid_at = Donation.Status.PAID, timezone.now()
            donation.save(update_fields=["status", "paid_at"])
            receipt = freeze(donation)
            audit.record(None, "donation.paid", makerspace=donation.makerspace, target=donation, meta={
                "donation_id": donation.pk, "status": status, "tax_receipt": bool(receipt)})
            notify_receipt(donation)
        else:
            donation.status, donation.cancelled_at = Donation.Status.CANCELLED, timezone.now()
            donation.save(update_fields=["status", "cancelled_at"])
            audit.record(None, "donation.cancelled", makerspace=donation.makerspace, target=donation,
                         meta={"donation_id": donation.pk, "status": status})
    return donation


def mark_sponsorship(payment_id, charge_id, status):
    from .models import SponsorshipCharge

    charge = SponsorshipCharge.objects.select_related("makerspace").filter(pk=charge_id).first()
    if charge is not None and status in SETTLED:
        audit.record(None, "sponsor.charge_paid", makerspace=charge.makerspace, target=charge, meta={
            "sponsor_id": charge.sponsor_id, "charge_id": charge.pk, "payment_id": payment_id, "status": status})

"""Raising, recording and cancelling gifts. No function here moves money (#59).

Every gift raises ONE `Payment` (subject `donation`) through the record-first ledger seam
`create_payment`; the income then shows in the finance ledger under the `donations` domain
(#94) from the charge's own settlement, so nothing is written to the ledger twice. An online
checkout is put on top only when `payments.donations` and credentials allow it; otherwise the
gift waits for an offline `ManualSettlement` receipt (maker-checker honoured).
"""

import logging
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.audit import services as audit

from .models import Donation, DonationCampaign, DonationSettings

logger = logging.getLogger(__name__)


def space_currency(space):
    from apps.payments.models import MakerspacePaymentSettings

    return MakerspacePaymentSettings.for_makerspace(space).default_currency


def clean_amount(space, raw):
    try:
        amount = Decimal(str(raw)).quantize(Decimal("0.01"))
    except (InvalidOperation, TypeError, ValueError):
        raise ValidationError({"amount": "Enter an amount.", "code": "amount_invalid"})
    minimum = DonationSettings.for_makerspace(space).minimum_amount
    if amount < minimum or amount > Decimal("9999999999.99"):
        raise ValidationError({"amount": f"The smallest gift here is {minimum}.", "code": "amount_below_minimum"})
    return amount


def open_campaign(space, campaign_id, *, staff=False):
    """The campaign or fund a gift goes to, or None. Donors only reach live, public ones."""
    if not campaign_id:
        return None
    campaign = DonationCampaign.objects.filter(pk=campaign_id, makerspace=space).first()
    now = timezone.now()
    if campaign is None or (not staff and (
            not campaign.is_active or not campaign.is_public
            or (campaign.starts_at and campaign.starts_at > now) or (campaign.ends_at and campaign.ends_at <= now))):
        raise ValidationError({"campaign": "This campaign is not open for gifts.", "code": "campaign_closed"})
    return campaign


@transaction.atomic
def create_gift(space, donor, *, amount, campaign=None, note="", tax=(False, "", ""),
                source=Donation.Source.ONLINE, pledge=None, period_start=None, actor=None):
    """One gift and its charge. Returns `(donation, payment)`."""
    from apps.payments.models import Payment
    from apps.payments.services import create_payment
    from apps.tenant_migration.gate_runtime import assert_write_allowed

    assert_write_allowed(space.pk)
    wants, pan, address = tax
    donation = Donation(
        makerspace=space, campaign=campaign, pledge=pledge, period_start=period_start, donor=donor.account,
        donor_name=donor.name, donor_email=donor.email, donor_note=(note or "").strip()[:500], amount=amount,
        currency=space_currency(space), source=source, wants_tax_receipt=wants, donor_pan=pan,
        donor_address=address, created_by=actor or donor.actor)
    donation.save()
    label = f"Donation: {campaign.name}" if campaign else f"Donation to {space.name}"
    payment = create_payment(
        makerspace=space, subject_type=Payment.SubjectType.DONATION, subject_id=donation.pk, member=donor.account,
        amount=amount, currency=donation.currency, created_by=actor or donor.actor, subject_label=label[:255])
    audit.record(actor or donor.account, "donation.created", makerspace=space, target=donation, meta={
        "donation_id": donation.pk, "payment_id": payment.pk, "amount": str(amount), "currency": donation.currency,
        "source": source, "campaign_id": getattr(campaign, "pk", None), "pledge_id": getattr(pledge, "pk", None),
        "guest": donor.is_guest, "tax_receipt_requested": wants})
    return donation, payment


def checkout_url(payment):
    """A hosted checkout for the gift's charge, or "" when the rail is off or failed (debt kept)."""
    from apps.payments.availability import online_payments_enabled
    from apps.payments.services import create_checkout_url

    if payment.status != "pending" or not online_payments_enabled(payment.makerspace, "donations"):
        return ""
    try:
        return create_checkout_url(payment.pk) or ""
    except Exception:  # noqa: BLE001 - a provider failure never loses the recorded gift
        logger.warning("donation_checkout_failed", extra={"payment_id": payment.pk})
        return ""


def record_desk_gift(space, donor, *, actor, amount, settlement, campaign=None, note="", tax=(False, "", "")):
    """Staff record a gift received in person: the charge plus its offline receipt, in one go."""
    from apps.payments.models import Payment
    from apps.payments.reconciliation import reconcile_payments

    with transaction.atomic():
        donation, payment = create_gift(space, donor, amount=amount, campaign=campaign, note=note, tax=tax,
                                              source=Donation.Source.DESK, actor=actor)
        reconcile_payments(actor=actor, makerspace_id=space.pk, payment_ids=[payment.pk],
                           target_status=Payment.Status.PAID_OFFLINE, settlement=settlement)
    donation.refresh_from_db()
    return donation


@transaction.atomic
def cancel_gift(donation, *, actor, reason=""):
    """Cancel a gift still waiting for payment. A received gift goes back only through a case."""
    from apps.payments.reconciliation import cancel_pending

    locked = Donation.objects.select_for_update().get(pk=donation.pk)
    if locked.status != Donation.Status.PENDING:
        raise ValidationError({"detail": "Only a gift waiting for payment can be cancelled.",
                               "code": "donation_not_pending"})
    cancel_pending(makerspace=locked.makerspace, subject_type="donation", subject_id=locked.pk, actor=actor)
    locked.status, locked.cancelled_at = Donation.Status.CANCELLED, timezone.now()
    locked.save(update_fields=["status", "cancelled_at"])
    audit.record(actor, "donation.cancelled", makerspace=locked.makerspace, target=locked,
                 meta={"donation_id": locked.pk, "reason_given": bool(reason)})
    return locked

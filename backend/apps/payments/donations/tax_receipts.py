"""Tax-exempt (India 80G) donation receipts (#128 C-14d).

* Optional per space: `finance.tax_exempt_receipts` plus a registration number and its
  validity on `DonationSettings` (finance settings, Space Manager only).
* The donor's PAN is collected only when they ask for an 80G receipt, validated, stored
  ALWAYS encrypted, shown masked everywhere but the receipt itself, and never exported to a
  report. A superadmin without a PII window sees it masked like any other scoped PII.
* The receipt is frozen once, when the gift is received, while the registration was valid
  on that day: the registration, its validity, the receipt number, amount and date. Never the
  PAN, name or address: those stay in the encrypted columns and are read when it is rendered.
"""

import re

from django.utils import timezone
from rest_framework.exceptions import ValidationError

PAN_RE = re.compile(r"^[A-Z]{5}[0-9]{4}[A-Z]$")
SECTION = "80G"


def normalize_pan(value):
    return re.sub(r"\s+", "", str(value or "")).upper()


def mask_pan(value):
    value = str(value or "")
    return f"••••••{value[-4:]}" if len(value) == 10 else ""


def registration_live(settings, on_date):
    if not settings.tax_exempt_registration_number:
        return False
    if settings.tax_exempt_valid_from and on_date < settings.tax_exempt_valid_from:
        return False
    return not (settings.tax_exempt_valid_until and on_date > settings.tax_exempt_valid_until)


def clean_request(space, data):
    """(wants, pan, address) from a donor's form; refuses an 80G request the space cannot honour."""
    from apps.makerspaces.platform import feature_enabled

    from .models import DonationSettings

    if not data.get("wants_tax_receipt"):
        return False, "", ""
    settings = DonationSettings.for_makerspace(space)
    if not feature_enabled(space, "finance.tax_exempt_receipts") or not registration_live(
            settings, timezone.localdate()):
        raise ValidationError({"wants_tax_receipt": "This space does not issue tax-exempt receipts.",
                               "code": "tax_receipts_unavailable"})
    pan = normalize_pan(data.get("donor_pan"))
    if not PAN_RE.match(pan):
        raise ValidationError({"donor_pan": "Enter a valid 10-character PAN.", "code": "pan_invalid"})
    address = str(data.get("donor_address") or "").strip()[:500]
    if not address:
        raise ValidationError({"donor_address": "An 80G receipt needs your postal address."})
    return True, pan, address


def receipt_number(donation):
    from apps.payments.models import PaymentDocument

    payment = payment_for(donation)
    number = PaymentDocument.objects.filter(
        payment=payment, kind="receipt", reverses__isnull=True).order_by("pk").values_list(
        "number", flat=True).first() if payment else None
    return number or f"{SECTION}-{donation.makerspace_id}-{donation.pk:06d}"


def payment_for(donation):
    from apps.payments.models import Payment

    return Payment.objects.filter(makerspace_id=donation.makerspace_id, subject_type="donation",
                                  subject_id=donation.pk).first()


def freeze(donation):
    """Freeze the 80G receipt on a received gift; returns it, or None when not owed."""
    from apps.makerspaces.platform import feature_enabled

    from .models import DonationSettings

    if not donation.wants_tax_receipt or donation.tax_receipt is not None or donation.paid_at is None:
        return donation.tax_receipt
    space = donation.makerspace
    settings = DonationSettings.for_makerspace(space)
    received_on = timezone.localdate(donation.paid_at)
    if not feature_enabled(space, "finance.tax_exempt_receipts") or not registration_live(settings, received_on):
        return None
    donation.tax_receipt = {
        "section": SECTION, "number": receipt_number(donation),
        "registration_number": settings.tax_exempt_registration_number,
        "valid_from": settings.tax_exempt_valid_from.isoformat() if settings.tax_exempt_valid_from else "",
        "valid_until": settings.tax_exempt_valid_until.isoformat() if settings.tax_exempt_valid_until else "",
        "registrant_pan": settings.tax_exempt_registrant_pan, "note": settings.tax_exempt_note,
        "amount": str(donation.amount), "currency": donation.currency, "received_on": received_on.isoformat(),
        "issued_at": timezone.now().isoformat(),
    }
    donation.save(update_fields=["tax_receipt"])
    return donation.tax_receipt

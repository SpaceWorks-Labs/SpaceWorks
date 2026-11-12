"""Tax-exempt donation receipts (#128 C-14d, generalised to any scheme by decision 242(m)).

* Optional per space: `finance.tax_exempt_receipts`, the non-profit profile switched on and a
  live deductible exemption (`nonprofit.receipt_exemptions`): India 80G, US 501(c)(3), a UK,
  Canadian or Australian charity number, or another scheme. Settings are the Space Manager's.
* India 80G asks the giver for their PAN and postal address. The PAN is validated, stored
  ALWAYS encrypted, shown masked everywhere but the receipt itself, and never exported to a
  report. A superadmin without a PII window sees it masked like any other scoped PII.
* The receipt is frozen once, when the gift is received, under the exemptions live that day:
  the legal identity, the exemptions, the signatory, the receipt number, amount and date. Never
  the PAN, name or address: those stay in the encrypted columns and are read when it is rendered.
"""

from django.utils.translation import gettext
import re

from django.utils import timezone

from . import nonprofit
from .gates import DonationRefused

PAN_RE = re.compile(r"^[A-Z]{5}[0-9]{4}[A-Z]$")
SECTION = "80G"


def normalize_pan(value):
    return re.sub(r"\s+", "", str(value or "")).upper()


def mask_pan(value):
    value = str(value or "")
    return f"••••••{value[-4:]}" if len(value) == 10 else ""


def registration_live(settings, on_date):
    """Kept for older callers: a tax receipt could be issued on `on_date` (any scheme)."""
    return bool(nonprofit.receipt_exemptions(settings, on_date))


def clean_request(space, data):
    """(wants, pan, address) from a giver's form; refuses a request the space cannot honour."""
    from .models import DonationSettings

    if not data.get("wants_tax_receipt"):
        return False, "", ""
    settings = DonationSettings.for_makerspace(space)
    today = timezone.localdate()
    if not nonprofit.receipts_available(space, settings, today):
        raise DonationRefused(gettext("This space does not issue tax receipts."), "tax_receipts_unavailable",
                              "wants_tax_receipt")
    address = str(data.get("donor_address") or "").strip()[:500]
    if not nonprofit.needs_pan(nonprofit.receipt_exemptions(settings, today)):
        return True, "", address
    pan = normalize_pan(data.get("donor_pan"))
    if not PAN_RE.match(pan):
        raise DonationRefused(gettext("Enter a valid 10-character PAN."), "pan_invalid", "donor_pan")
    if not address:
        raise DonationRefused(gettext("An 80G receipt needs your postal address."), "address_required", "donor_address")
    return True, pan, address


def receipt_number(donation, prefix=SECTION):
    from apps.payments.models import PaymentDocument

    payment = payment_for(donation)
    number = PaymentDocument.objects.filter(
        payment=payment, kind="receipt", reverses__isnull=True).order_by("pk").values_list(
        "number", flat=True).first() if payment else None
    return number or f"{prefix}-{donation.makerspace_id}-{donation.pk:06d}"


def payment_for(donation):
    from apps.payments.models import Payment

    return Payment.objects.filter(makerspace_id=donation.makerspace_id, subject_type="donation",
                                  subject_id=donation.pk).first()


def freeze(donation):
    """Freeze the tax receipt on a received gift; returns it, or None when none is owed."""
    from .models import DonationSettings

    if not donation.wants_tax_receipt or donation.tax_receipt is not None or donation.paid_at is None:
        return donation.tax_receipt
    space = donation.makerspace
    settings = DonationSettings.for_makerspace(space)
    received_on = timezone.localdate(donation.paid_at)
    if not nonprofit.receipts_available(space, settings, received_on):
        return None
    rows = nonprofit.receipt_exemptions(settings, received_on)
    india = next((row for row in rows if row["scheme"] == nonprofit.INDIA_80G), None)
    primary = india or rows[0]
    donation.tax_receipt = {
        # The first five keys are the 80G shape older receipts and readers already know.
        "section": SECTION if india else nonprofit.label(primary["scheme"]),
        "number": receipt_number(donation, SECTION if india else "TR"),
        "registration_number": primary["number"], "valid_from": primary.get("valid_from", ""),
        "valid_until": primary.get("valid_until", ""),
        "registrant_pan": settings.tax_exempt_registrant_pan if india else "", "note": settings.tax_exempt_note,
        "exemptions": [{"scheme": row["scheme"], "label": nonprofit.label(row["scheme"]), "number": row["number"],
                        "valid_from": row.get("valid_from", ""), "valid_until": row.get("valid_until", "")}
                       for row in rows],
        "legal_name": settings.legal_name, "organization_registration_number": settings.organization_registration_number,
        "signatory_name": settings.signatory_name, "signatory_title": settings.signatory_title,
        "footer": settings.receipt_footer,
        "amount": str(donation.amount), "currency": donation.currency, "received_on": received_on.isoformat(),
        "issued_at": timezone.now().isoformat(),
    }
    donation.save(update_fields=["tax_receipt"])
    return donation.tax_receipt


def receipt_note(donation):
    """What the giver is told about their receipt (decision 242(m))."""
    from django.utils.translation import gettext

    if donation.tax_receipt:
        return ""
    return gettext(nonprofit.NOT_A_TAX_RECEIPT)

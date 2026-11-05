"""Hack-money G7 (#181): prize tax is RECORD ONLY.

The space's setting (`payments.EventMoneySettings`, off by default) PROPOSES tax deducted at source
on a prize payout whose gross is above the threshold, at the rate (defaults 30% above 10,000).
Staff accept or change it when recording the payout; the payout stores gross, TDS and net. Staff
deduct and file outside SpaceWorks: no certificates and no filing reports are made here.

A winner's PAN is collected on their claim, always encrypted, and only ever shown masked
(`••••••1234`). It never enters audit metadata, exports, reports or analytics.
"""

from decimal import ROUND_HALF_UP, Decimal

from apps.payments.donations.tax_receipts import PAN_RE, mask_pan, normalize_pan

__all__ = ("PAN_RE", "mask_pan", "normalize_pan", "proposed_tds", "tax_settings", "clean_pan")
CENT = Decimal("0.01")


def tax_settings(makerspace):
    from apps.payments.models import EventMoneySettings
    return EventMoneySettings.for_makerspace(makerspace)


def proposed_tds(makerspace, gross):
    """The deduction the space's setting proposes for one payout (0.00 when off or not above the threshold)."""
    settings = tax_settings(makerspace)
    gross = Decimal(gross)
    if not settings.prize_tds_enabled or gross <= settings.prize_tds_threshold:
        return Decimal("0.00")
    return (gross * settings.prize_tds_rate / Decimal(100)).quantize(CENT, rounding=ROUND_HALF_UP)


def clean_pan(value):
    """Normalise and check an Indian PAN; "" stays "" (a PAN is asked for, never required)."""
    from rest_framework.exceptions import ValidationError
    pan = normalize_pan(value)
    if pan and not PAN_RE.match(pan):
        raise ValidationError({"pan": "Enter a valid PAN (five letters, four digits, one letter)."})
    return pan

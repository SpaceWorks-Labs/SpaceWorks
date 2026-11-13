"""The non-profit profile (decision 242(m)): who may issue tax receipts, under which schemes.

A space is a non-profit when the Space Manager says so (`DonationSettings.is_nonprofit`). Its
tax-exemption IDs are a typed list -- scheme, number and an optional validity window -- and a tax
receipt can be issued only while the space is a non-profit, `finance.tax_exempt_receipts` is on
and at least one DEDUCTIBLE scheme is live on the day the gift was received. India 12A is the
trust's own registration, not a donor deduction: it is printed, but it unlocks nothing alone.

Off, giving still works; every receipt the giver sees says it is not a tax receipt, and the
public pages show no Donate entry.
"""

from datetime import date

from django.utils.translation import gettext, gettext_noop
from rest_framework import serializers

#: scheme -> (label, deductible). Labels are plain language; the key is stored.
SCHEMES = {
    "in_80g": (gettext_noop("India: section 80G"), True),
    "in_12a": (gettext_noop("India: section 12A/12AB registration"), False),
    "us_501c3": (gettext_noop("United States: 501(c)(3)"), True),
    "uk_charity": (gettext_noop("United Kingdom: registered charity"), True),
    "ca_charity": (gettext_noop("Canada: registered charity"), True),
    "au_dgr": (gettext_noop("Australia: deductible gift recipient"), True),
    "other": (gettext_noop("Other tax-exemption registration"), True),
}
INDIA_80G = "in_80g"
MAX_EXEMPTIONS = 10
NOT_A_TAX_RECEIPT = gettext_noop("This is a receipt for your gift. It is not a tax receipt.")


def label(scheme):
    return gettext(SCHEMES.get(scheme, SCHEMES["other"])[0])


def _day(value):
    if not value:
        return None
    return value if isinstance(value, date) else date.fromisoformat(str(value))


def clean_exemptions(value):
    """Validate the typed list from the settings form; returns it normalised (ISO dates)."""
    if not isinstance(value, list) or len(value) > MAX_EXEMPTIONS:
        raise serializers.ValidationError(gettext("Give up to 10 tax-exemption registrations."))
    cleaned = []
    for row in value:
        if not isinstance(row, dict) or row.get("scheme") not in SCHEMES:
            raise serializers.ValidationError(gettext("Choose a scheme for every registration."))
        number = str(row.get("number") or "").strip()
        if not number or len(number) > 64:
            raise serializers.ValidationError(gettext("Every registration needs its number (up to 64 characters)."))
        try:
            start, end = _day(row.get("valid_from")), _day(row.get("valid_until"))
        except ValueError:
            raise serializers.ValidationError(gettext("Enter validity dates as YYYY-MM-DD."))
        if start and end and end < start:
            raise serializers.ValidationError(gettext("A registration's validity must end after it starts."))
        cleaned.append({"scheme": row["scheme"], "number": number,
                        "valid_from": start.isoformat() if start else "",
                        "valid_until": end.isoformat() if end else ""})
    return cleaned


def live(row, on_date):
    start, end = _day(row.get("valid_from")), _day(row.get("valid_until"))
    return not (start and on_date < start) and not (end and on_date > end)


def receipt_exemptions(settings, on_date):
    """Live exemptions a tax receipt may cite on `on_date`; empty unless a deductible one is live."""
    if not settings.is_nonprofit:
        return []
    rows = [row for row in (settings.tax_exemptions or []) if isinstance(row, dict) and live(row, on_date)]
    return rows if any(SCHEMES.get(row.get("scheme"), ("", False))[1] for row in rows) else []


def receipts_available(space, settings, on_date):
    from apps.makerspaces.platform import feature_enabled

    return feature_enabled(space, "finance.tax_exempt_receipts") and bool(receipt_exemptions(settings, on_date))


def needs_pan(rows):
    """India 80G asks the giver for their PAN and postal address; other schemes do not."""
    return any(row.get("scheme") == INDIA_80G for row in rows)


def mirror_legacy_80g(settings):
    """Keep the single-80G columns a mirror of the list (and adopt them while the list is empty).

    Returns the changed column names. A writer that only knows the old columns (an older
    fixture or command) still produces one India 80G entry; the settings form, which writes the
    list, clears the old columns itself when it empties the list.
    """
    fields = ("tax_exempt_registration_number", "tax_exempt_valid_from", "tax_exempt_valid_until")
    rows = settings.tax_exemptions or []
    if not rows and settings.tax_exempt_registration_number:
        settings.tax_exemptions = [{
            "scheme": INDIA_80G, "number": settings.tax_exempt_registration_number,
            "valid_from": settings.tax_exempt_valid_from.isoformat() if settings.tax_exempt_valid_from else "",
            "valid_until": settings.tax_exempt_valid_until.isoformat() if settings.tax_exempt_valid_until else ""}]
        return ["tax_exemptions"]
    first = next((row for row in rows if isinstance(row, dict) and row.get("scheme") == INDIA_80G), None)
    target = ("", None, None)
    if first:
        target = (first["number"], _day(first.get("valid_from")), _day(first.get("valid_until")))
    current = tuple(getattr(settings, name) for name in fields)
    if current == target:
        return []
    for name, value in zip(fields, target):
        setattr(settings, name, value)
    return list(fields)


def public_profile(settings):
    """What the public donation page may show: the space's own legal identity, never a person's."""
    if not settings.is_nonprofit:
        return {"is_nonprofit": False, "legal_name": "", "registration_number": "", "exemptions": []}
    return {"is_nonprofit": True, "legal_name": settings.legal_name,
            "registration_number": settings.organization_registration_number,
            "exemptions": [{"scheme": row["scheme"], "label": label(row["scheme"]), "number": row["number"]}
                           for row in settings.tax_exemptions or [] if isinstance(row, dict) and row.get("scheme")]}


def donate_entry_enabled(space):
    """The public Donate entry: donations on, money being recorded and the space a non-profit."""
    from apps.makerspaces.platform import feature_enabled
    from apps.payments.availability import charge_tracking_enabled

    from .models import DonationSettings

    if not feature_enabled(space, "finance.donations") or not charge_tracking_enabled(space, "donations"):
        return False
    return DonationSettings.objects.filter(makerspace=space, is_nonprofit=True).exists()

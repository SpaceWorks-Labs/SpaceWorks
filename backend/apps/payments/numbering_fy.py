"""Per-financial-year gapless document numbers (CGST Rule 46).

Used only when the space's tax policy is live at issue time. Every other space keeps the
single release-1 series in `MakerspaceBillingSettings.next_document_number` untouched,
so switching tax on never renumbers an issued document; it only starts the FY series
for documents issued from then on.

Format: `<prefix><FY>/<number>`, e.g. `INV26-27/0001`. The prefix is at most four
characters, receipts (tax invoices) and credit notes run separate series, and a number
never exceeds 16 characters -- the series refuses to issue rather than print a number
the law does not allow.
"""

from dataclasses import dataclass

from apps.makerspaces.local_time import local_now
from apps.payments.tax.fy import fy_short, fy_start
from apps.payments.tax.models_tax import DocumentNumberCounter

MAX_LENGTH = 16


class NumberingExhausted(ValueError):
    pass


@dataclass(frozen=True)
class FyNumber:
    series: str
    fy_start: object
    sequence: int
    number: str


def series_for(kind):
    return DocumentNumberCounter.Series.CREDIT_NOTE if kind == "credit_note" else DocumentNumberCounter.Series.INVOICE


def format_number(prefix, start, sequence):
    number = f"{prefix}{fy_short(start)}/{sequence:04d}"
    if len(number) > MAX_LENGTH:
        raise NumberingExhausted("This financial year's document series is full.")
    return number


def allocate(space, policy, kind, *, taken):
    """Lock this FY's counter for the series and reserve the next free number.

    Caller holds the tenant row lock and the issue transaction, so a rollback returns the
    number and the series stays gapless. `taken(number)` skips numbers an import already
    used, exactly as the release-1 series does.
    """
    series = series_for(kind)
    prefix = policy.credit_note_prefix if series == DocumentNumberCounter.Series.CREDIT_NOTE else policy.invoice_prefix
    return allocate_in_series(space, series, prefix, taken=taken)


def allocate_in_series(space, series, prefix, *, taken):
    """The same locked, gapless allocation for any counter series (parity O-B3 adds `receipt`)."""
    start = fy_start(space, local_now(space).date())
    counter, _ = DocumentNumberCounter.objects.get_or_create(makerspace=space, series=series, fy_start=start)
    counter = DocumentNumberCounter.objects.select_for_update().get(pk=counter.pk)
    sequence = counter.next_number
    while taken(format_number(prefix, start, sequence)):
        sequence += 1
    number = format_number(prefix, start, sequence)
    counter.next_number = sequence + 1
    counter.save(update_fields=["next_number"])
    return FyNumber(series, start, sequence, number)

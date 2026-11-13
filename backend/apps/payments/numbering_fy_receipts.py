"""Per-financial-year receipt numbers for a space that charges no tax (parity O-B3, `billing.fy_receipts`).

A space with the tax policy live already numbers its receipts per FY (`numbering_fy`). With this switch a
space WITHOUT tax gets the same gapless series for plain receipts, in its own counter series (`receipt`):
`R26-27/0001`. The day the switch is turned on is the cut-over: receipts already issued keep their release-1
numbers, so nothing is ever renumbered. Bills and credit notes keep their own series.

The prefix is the space's receipt prefix when it is 1 to 4 characters of capitals, digits, '-' or '/', else
`R`: a FY number must stay within 16 characters, and a receipt that cannot be issued would block settling.
"""

from apps.audit import services as audit
from apps.makerspaces.platform import feature_enabled
from apps.payments.numbering_fy import FyNumber, allocate_in_series
from apps.payments.tax.models_tax import DocumentNumberCounter

DEFAULT_PREFIX = "R"
_ALLOWED = set("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-/")


def prefix_for(policy):
    value = (policy.number_prefix or "").strip()
    return value if 1 <= len(value) <= 4 and set(value) <= _ALLOWED else DEFAULT_PREFIX


def applies(space, kind):
    """A plain receipt, tax off (the caller has already found no tax plan), switch on."""
    return kind == "receipt" and feature_enabled(space, "billing.fy_receipts")


def allocate_receipt(space, policy, *, taken, actor=None):
    """Reserve the next receipt number of this FY; audit the first one ever (the cut-over)."""
    first = not DocumentNumberCounter.objects.filter(
        makerspace=space, series=DocumentNumberCounter.Series.RECEIPT).exists()
    number: FyNumber = allocate_in_series(space, DocumentNumberCounter.Series.RECEIPT, prefix_for(policy),
                                          taken=taken)
    if first:
        audit.record(actor, "billing.fy_receipts_enabled", makerspace=space, target=space,
                     meta={"fy_start": number.fy_start.isoformat(), "first_number": number.number})
    return number

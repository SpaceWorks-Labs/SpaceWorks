"""Parity O-B3: per-FY receipt numbers, plan SAC codes and the collection sheet. Counts and ids only: never an
amount, a payer, a reference or a SAC code itself."""

from django.utils.translation import gettext_noop
from .presentation_catalog_types import P

ENTRIES = (
    P("billing.fy_receipts_enabled", gettext_noop("Receipts now numbered per financial year"),
      ("fy_start", "first_number")),
    P("membership_plan.sac_changed", gettext_noop("Membership plan SAC code changed"), ("plan_id", "cleared")),
    P("payment.collection_sheet_recorded", gettext_noop("Collection sheet recorded"),
      ("rows", "recorded", "awaiting_confirmation", "failed")),
    P("payment.cash_handover_recorded", gettext_noop("Cash handed over"), ("collector_id", "currency")),
)

"""Release-2 lane L24: price-drop refunds (#163A).

One row per price save that opened refund cases: the area, how many items, and the case
and charge ids. Each case also writes its own `payment.refund_case_opened` row; members
are never named here."""

from django.utils.translation import gettext_lazy
from .presentation_catalog_types import P

ENTRIES = (
    P("pricing.price_drop_refunds_opened", gettext_lazy("Refund cases opened after a price drop"),
      ("area", "items", "case_ids", "payment_ids")),
)

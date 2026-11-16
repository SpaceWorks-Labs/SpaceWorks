"""The one seam every price save calls after it has written the new price (#163A).

`on_price_change(actor, makerspace, area, target=..., find=...)` runs inside the save's
own transaction, so the finder re-prices items under the price just written:

* during a preview (`?price_drop_preview=1`) the affected items are collected and the
  save is rolled back by the view (`preview.py`); with the switch off that is a 404;
* on a real save with `charges.price_drop_refunds` on, each affected item gets its
  refund case through `add_due_share` -- an open case on the same charge grows instead
  (one active case per charge, R1) -- and ONE `pricing.price_drop_refunds_opened` audit
  row names the cases. Each case also writes its own `payment.refund_case_opened`;
* with the switch off a save opens nothing (the finder is not even run).

No money moves here: every case waits for the Space Manager or a finance admin.
"""

from apps.audit import services as audit
from apps.makerspaces.platform import feature_enabled
from apps.payments.models import RefundCase
from apps.payments.price_drop import FEATURE
from apps.payments.price_drop.preview import PreviewUnavailable, active_collector


def open_share(affected, *, actor, reason_code, source):
    from apps.payments.services_refund_partial import add_due_share
    return add_due_share(affected.payment, amount=affected.difference, reason_code=reason_code, actor=actor,
                         snapshot={"source": source, "item": affected.item, "area": affected.area,
                                   "before": str(affected.before), "after": str(affected.after), **affected.facts})


def on_price_change(actor, makerspace, area, *, target, find):
    """Collect (preview) or open (save) the price-drop cases one price save causes."""
    collector = active_collector()
    enabled = feature_enabled(makerspace, FEATURE)
    if collector is not None:
        if not enabled:
            raise PreviewUnavailable()
        collector.items.extend(find())
        return []
    if not enabled:
        return []
    items = list(find())
    if not items:
        return []
    cases = []
    for affected in items:
        case = open_share(affected, actor=actor, reason_code=RefundCase.ReasonCode.PRICE_DROP, source="price_drop")
        if case is not None:
            cases.append(case)
    audit.record(actor, "pricing.price_drop_refunds_opened", makerspace=makerspace, target=target, meta={
        "area": area, "items": len(items), "case_ids": sorted({case.pk for case in cases}),
        "payment_ids": sorted({affected.payment.pk for affected in items}),
    })
    return cases

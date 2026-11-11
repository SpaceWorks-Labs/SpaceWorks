"""Parity O-B3: money add-ons for community organisations (all parentless, like the other `billing.*` keys).

* `billing.fy_receipts` -- number receipts per financial year (`R26-27/0001`) even while tax is off. The day
  it is switched on is the cut-over: documents already issued are never renumbered. OFF by default.
* `billing.plan_sac` -- a membership plan may carry its own SAC code, frozen on the GST charge it raises. Needs
  `billing.tax`. OFF by default; plans keep the code when it is switched off.
* `billing.collection_sheet` -- record up to 200 offline payments in one sheet. Every row still goes through
  the offline settlement service, so the two-person check stays in force. OFF by default.
"""


def definitions(feature):
    return (
        feature("billing.fy_receipts", None, "Receipt numbers per financial year",
                "Number receipts per financial year (for example R26-27/0001) even when no tax is charged. "
                "Receipts already issued keep their numbers.",
                requires_features=("billing.documents",)),
        feature("billing.plan_sac", None, "SAC code per membership plan",
                "Give a membership plan its own SAC code for GST invoices instead of the space-wide one.",
                requires_features=("billing.tax",)),
        feature("billing.collection_sheet", None, "Collection sheet",
                "Record up to 200 cash, UPI, bank or cheque payments in one sheet, each one settled and "
                "confirmed like a single payment."),
    )

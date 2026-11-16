"""Release-2 lane L24: price-drop refunds (#163A).

* `charges.price_drop_refunds` -- when staff LOWER a price after people already paid,
  the save shows the affected paid, not-yet-used items (upcoming bookings, tickets for
  events not yet held, prepaid machine jobs not yet started, membership terms not yet
  started) with the difference, and opens one staff-approved refund case per item. The
  Space Manager or a finance admin (view_finance plus record_payment) approves each one;
  nothing is refunded automatically, and a price RISE never charges anyone more.
  Parentless, like `charges.pricing`: it decides what is OWED back, which never depends
  on the removable payments rail. OFF by default. Off: no preview, no cases; cases
  already opened stay in the refund queue.

The prepaid machine-job cases of #171 (a member cancels before the job starts; the
actual cost comes in below the quote) are NOT behind this key: they are always on
wherever machine charging is on.
"""


def definitions(feature):
    return (
        feature(
            "charges.price_drop_refunds", None, "Price-drop refunds",
            "When a price is lowered after people paid, staff see the affected paid, not-yet-used "
            "bookings, tickets, prepaid machine jobs and membership terms with the difference, and a "
            "refund case opens for each one. The Space Manager or a finance admin approves every refund.",
        ),
    )

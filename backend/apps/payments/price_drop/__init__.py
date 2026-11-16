"""Price-drop refunds (lane L24, #163A) and the prepaid-job difference cases (#171).

When staff LOWER a price after people already paid, every paid, not-yet-used item that
would now cost less gets a staff-approved `RefundCase` for the difference:

* upcoming BOOKINGS (rooms and machine time) -- `find_bookings`;
* EVENT TICKETS for events not yet held -- `find_tickets`;
* MACHINE JOB quotes for prepaid jobs not yet started -- `find_jobs`;
* MEMBERSHIP FEES for terms not yet started -- `find_membership`.

The rules:

* nothing is refunded automatically: each case waits for the Space Manager or a finance
  admin (view_finance plus record_payment) -- `approval.py`;
* a price RISE never charges anyone more: quotes are frozen (#159, L15), so a rise finds
  nothing here;
* the difference is computed from the frozen quote, never from today's list price, and
  never exceeds what is left to refund on the charge; a second drop offers only the
  further difference (`shares.py` reads the earlier offers back from the cases);
* `charges.price_drop_refunds` (default off) gates the price-drop cases only. With it off
  a save opens nothing and the preview answers 404. The #171 job cases are always on
  wherever machine charging is on (`apps.machines.job_refunds`).

Staff see the affected items before saving: every price-saving endpoint accepts
`?price_drop_preview=1`, which runs the save, collects the affected items and rolls the
whole save back (`preview.py`).
"""

FEATURE = "charges.price_drop_refunds"
#: `policy_snapshot.shares[].source` values L24 writes; each also lowers the item's baseline.
SOURCES = ("price_drop", "quote_difference")

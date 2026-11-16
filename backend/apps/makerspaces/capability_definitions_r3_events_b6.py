"""Parity E-B6: refunds that cancel the tickets, and staff expense claims (both OFF by default).

* `events.refund_cancels_tickets` -- when staff approve a refund on a ticket order they may also cancel the
  tickets it paid for. Without it an approved refund only returns money and the seats stay as they are.
* `events.staff_claims` -- staff file an expense claim for themselves or for a speaker or volunteer. It is
  paid from the event's reimbursement pool like every other claim, so the pool is the cap.

Data is kept when a switch is turned off; the feature disappears from the UI and answers 404.
"""


def definitions(feature):
    return (
        feature("events.refund_cancels_tickets", "events", "Refund can cancel tickets",
                "When a refund on a ticket order is approved, staff can also cancel the tickets that order paid "
                "for, so the seats are freed and the waitlist moves.", requires_features=("events.orders",)),
        feature("events.staff_claims", "events", "Staff expense claims",
                "Staff file an expense claim for themselves, or for a speaker or volunteer, from the event's "
                "reimbursement pool.", requires_modules=("event_reimbursements",)),
    )

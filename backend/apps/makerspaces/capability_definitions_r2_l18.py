"""Release-2 lane L18: donations, sponsors and calendar sync (#94, #95, #96, #128 C-14).

* `finance.*` (parentless, on the core ledger like `finance.ledger`; C-14a) -- each off by default:
  `finance.donations` (the donation page, one-off gifts, receipts), `finance.recurring_donations`
  (pledges that raise a charge each period, no card on file), `finance.sponsors` (sponsors, perks,
  sponsorship income and the opt-in sponsor wall) and `finance.tax_exempt_receipts` (80G receipts,
  the donor PAN encrypted).
* `payments.donations` -- the online rail for gifts and sponsor money; off means they are settled
  offline with a receipt. Like every `payments.*` key it is an additive AND in front of credentials.
* Calendar sync: `bookings.calendar_feed` and `events.calendar_feed` keep today's feeds (on by
  default, backfilled on for existing spaces); `events.shifts_feed` (a person's volunteer and mentor
  shifts), `calendar.combined_feed` (one per-person feed across bookings, events and shifts, C-14e)
  and `events.public_feed` (listed published events, C-14f) are new and off by default.
Switching any of them off keeps the data (#95, #128 C-8).
"""


def definitions(feature):
    return (
        feature("finance.donations", None, "Donations",
                "A donation page for the space, optional campaigns and funds, receipts, and gifts "
                "recorded by staff. Every gift is income in the finance ledger."),
        feature("finance.recurring_donations", None, "Recurring donations",
                "Donors pledge an amount every month, quarter or year; each period raises a charge "
                "they pay like any other. No card is stored.", requires_features=("finance.donations",)),
        feature("finance.sponsors", None, "Sponsors",
                "Sponsors with tiers, perk checklists, sponsorship income and an optional public "
                "sponsor wall."),
        feature("finance.tax_exempt_receipts", None, "Tax-exempt donation receipts",
                "Issue 80G receipts with the space's registration number. A donor's PAN is collected "
                "only when they ask for one and is always stored encrypted.",
                requires_features=("finance.donations",)),
        feature("payments.donations", "payments", "Donation payments",
                "Take donations and sponsor payments online. Off, they are recorded and settled "
                "offline with a receipt.", requires_features=("finance.donations",)),
        feature("bookings.calendar_feed", "bookings", "Booking calendar feed",
                "Members subscribe to their own bookings from a private calendar link.",
                default_enabled=True),
        feature("events.calendar_feed", "events", "Event calendar feed",
                "Members subscribe to their own event registrations from a private calendar link.",
                default_enabled=True),
        feature("events.shifts_feed", "events", "Shift calendar feed",
                "Volunteers and mentors subscribe to their own approved shifts from a private link."),
        feature("calendar.combined_feed", None, "Combined personal calendar",
                "One private calendar link per person with their bookings, event registrations and "
                "shifts in this space."),
        feature("events.public_feed", "events", "Public events calendar",
                "A public calendar of this space's listed, published events that anyone can subscribe to."),
    )

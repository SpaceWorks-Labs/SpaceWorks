"""Decision 223 (k), lane L3b: minors and guardian consent, volunteer credit, the attendee join funnel and
organization bookings.

* `membership.minors` -- record people under the age of majority and require a guardian's e-signed consent
  (versioned like a waiver) before membership, event registration, a guest pass, on-site check-in,
  borrowing or machine use, according to the space's minors settings. OFF by default, data kept when off.
* `membership.volunteer_credit` -- approved volunteer hours convert into a recorded credit applied to the
  next membership charge. Needs `membership`. Recorded as money owed, independent of the payments rail.
* `membership.join_funnel` -- the "Join" call to action after an event or on a guest pass, the opt-in
  follow-up notice, and the join-funnel report.
* `bookings.organization_bookings` -- staff book a space for an organization's partner event; the debt is
  recorded against the organization's contact member.
"""


def definitions(feature):
    return (
        feature("membership.minors", "membership", "Minors and guardian consent",
                "Record people under the age of majority and require a guardian's signed consent before they "
                "join, register, visit, borrow or use machines, as your minors settings decide."),
        feature("membership.volunteer_credit", "membership", "Volunteer hours as membership credit",
                "Members log volunteer hours, staff approve them, and approved hours earn a recorded credit "
                "on the next membership charge."),
        feature("membership.join_funnel", "membership", "Attendee join funnel",
                "Offer event attendees and guest-pass holders a pre-filled 'Join' request, send an opt-in "
                "follow-up after events, and report attendees, guests and joiners."),
        feature("bookings.organization_bookings", "bookings", "Organization bookings",
                "Book a space for an organization's partner event; the booking is recorded against the "
                "organization and its contact member."),
    )

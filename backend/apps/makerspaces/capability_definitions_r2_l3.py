"""Release-2 lane L3: ID cards (#128 C-12, #132, #133; SPEC §0.1 item 2).

Member cards themselves ride the `membership` module, as before. Every key here is
off by default and keeps its data when turned off (#95, #128 C-8).

* `membership.id_programmes` -- organisation ID programmes hosted by this space: join
  form, import, approvals, numbering, designs, bulk outputs and the public check.
* `membership.wallet_passes` -- Apple/Google Wallet passes for member and programme
  cards and (decision 223) guest passes; shown only once the space's own pass credentials
  or, failing those, the platform's exist (Q-I11, 223(l)).
* `events.id_cards` -- per-event ID cards for confirmed registrants, designed and
  published by the event's organisers with no approval (#128).
* `events.ticket_designs` -- the X49 ticket designer (per event and ticket type; the
  PDF attached to the confirmation email).
* `events.wallet_passes` -- wallet passes for event ID cards; needs `events.id_cards`.
"""


def definitions(feature):
    return (
        feature("membership.id_programmes", "membership", "ID programmes",
                "Organisation ID programmes: join form, import, approvals, numbered cards, designs and a "
                "public check page."),
        feature("membership.wallet_passes", "membership", "Wallet passes for member cards",
                "Apple and Google Wallet passes with live updates, once this space or the platform has signing credentials."),
        feature("events.id_cards", "events", "Event ID cards",
                "An ID card for every confirmed registrant, designed and published by the event's organisers."),
        feature("events.ticket_designs", "events", "Ticket designs",
                "Design event tickets per event and ticket type; the PDF goes with the confirmation email."),
        feature("events.wallet_passes", "events", "Wallet passes for event cards",
                "Apple and Google Wallet passes for event ID cards.", requires_features=("events.id_cards",)),
    )

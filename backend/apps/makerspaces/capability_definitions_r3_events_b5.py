"""Parity E-B5: series allowlists, the 24-hour pay window and per-event saved views (all OFF by default).

* `events.series_invites` -- an email allowlist on a series that admits that person to every occurrence.
* `events.pay_window` -- an approved, promoted or re-accepted paid place must be paid within 24 hours or it is
  released to the next person. Without it the existing 30-minute checkout hold and reminder are all there is.
* `events.event_saved_views` -- saved filters and counted presets that belong to one event's guest list.
  Check-in list additions (order, restore, undo, override, counts) ride the existing `events.checkin_lists`.

Data is kept when a switch is turned off; the feature disappears from the UI, answers 404 and does no scheduled work.
"""


def definitions(feature):
    return (
        feature("events.series_invites", "events", "Series invite lists",
                "Allow chosen emails to register for every occurrence of an invite-only series, including ones "
                "added later.", requires_features=("events.invites",)),
        feature("events.pay_window", "events", "24-hour payment window",
                "A paid place that staff approve, promote from the waitlist or re-accept is held for 24 hours. "
                "If it is not paid in time the place is released and the next person on the waitlist is offered it.",
                requires_features=("events.orders",)),
        feature("events.event_saved_views", "events", "Saved views for one event's guests",
                "Save and share filters on a single event's guest list, with ready-made presets that show counts.",
                requires_features=("events.saved_views",)),
    )

"""Decision 223: guest passes (a dated permit for an existing account, never a membership).

* `membership.guest_passes` -- the master switch. With it off no pass is issued and a live
  pass stops unlocking anything; recorded passes, loans and charges keep their normal
  return and settlement paths. OFF by default, data kept when turned off.
* `membership.day_passes` -- a paid or free day pass a guest buys or staff sell at the desk.
  Needs `membership.guest_passes`. The charge is recorded under `charges.membership` and
  never depends on the payments rail.
* `events.guest_passes` -- non-member registrants get an event pass automatically (the
  per-event setting is owned by the events adapter). Needs `membership.guest_passes`.
"""


def definitions(feature):
    return (
        feature("membership.guest_passes", "membership", "Guest passes",
                "Let people who are not members visit on a dated pass: invited by a member, issued for an "
                "event, or bought for a day. A pass is never a membership and is not counted as a member."),
        feature("membership.day_passes", "membership", "Day passes",
                "Sell or give a one-day pass. The price is recorded as money owed and can be paid online when "
                "online payments are on.", requires_features=("membership.guest_passes",)),
        feature("events.guest_passes", "events", "Event guest passes",
                "Give non-member registrants a pass for the event window when they check in.",
                requires_features=("membership.guest_passes",)),
    )

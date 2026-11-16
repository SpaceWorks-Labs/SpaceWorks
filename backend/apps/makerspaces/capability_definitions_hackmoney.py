"""Hack-money lane (#180): prize claims and splits, refundable deposits, add-ons for accepted places.

Every key is a capability under `events`, off by default, and keeps its data when turned off (#95).
Prize tax (#181 G7) is not a capability: it is the space's own prize-tax setting, off by default.

* `events.prize_claims` -- per-member prize splits and the winner claim flow: payee details and
  the winner's PAN (encrypted, masked), a claim window, forfeiture and "My prizes" (G3/G4/G6).
* `events.deposits` -- an optional refundable commitment deposit per hackathon, charged on
  confirmation and returned only through a staff-approved settlement batch (G10).
* `events.accepted_addons` -- people confirmed on an approval event may buy add-ons alone (G9).
"""


def definitions(feature):
    hackathons = ("events.hackathons",)
    return (
        feature("events.prize_claims", "events", "Prize splits and winner claims",
                "Winning teams split a prize between members, and each winner gives where to be paid (and a "
                "tax ID if the space records prize tax). Staff still record every payout by hand.",
                requires_features=("events.prize_payouts",)),
        feature("events.deposits", "events", "Refundable hackathon deposits",
                "Charge a refundable deposit when a place is confirmed. After the event staff approve a "
                "settlement batch that opens refund cases for people who came; no-shows keep the charge.",
                requires_features=hackathons),
        feature("events.accepted_addons", "events", "Add-ons for accepted participants",
                "On events that review registrations, people already confirmed can buy add-ons such as a "
                "T-shirt, meals or a hardware kit without buying another seat."),
    )

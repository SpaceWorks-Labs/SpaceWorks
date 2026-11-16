"""Release-2 lane L15: paid and free everywhere (#84, #85).

Three switches. Each keeps its data when turned off (#95, #128 C-8):

* `charges.pricing` -- rate cards per area (free or paid, rates, caps, grace, billing
  increments), per-item prices, loan rental, damage and lost charges, machine time AND
  material, per-hour bookings, the price preview. Parentless, like `charges.enabled`:
  pricing decides what is OWED, which never depends on the removable payments rail. ON
  by default: with nothing configured every new component is free, so a space that
  never opens the screen charges exactly what release 1 charged. Off: only the release-1
  price fields apply and the pricing screens and APIs are gone.
* `charges.discounts` -- automatic member discounts (all members, a plan's members, one
  member); one best rule per quote, then an event promo code. Off by default.
* `loans.fee_waivers` -- staff waive a loan's fees with a reason. Under lending (the core
  request workflow). On by default. Off hides the tools; waivers already written keep
  their loans free.
"""


def definitions(feature):
    return (
        feature(
            "charges.pricing", None, "Price lists",
            "Free or paid per area with rates, caps and billing increments; per-item prices; "
            "loan rental, damage and lost charges; machine time and material; hourly rooms; and "
            "the price preview members see before they commit.",
            default_enabled=True,
        ),
        feature(
            "charges.discounts", None, "Member discounts",
            "Automatic discounts for all members, the members on a plan, or one member. Only the "
            "single best discount applies, then an event promo code on top.",
            requires_features=("charges.pricing",),
        ),
        feature(
            "loans.fee_waivers", "request_workflow", "Waive loan fees",
            "Staff make a loan's rental, late, damage or lost fees free, with a recorded reason. A "
            "fee already paid opens a refund for staff approval; the deposit is never waived.",
            default_enabled=True,
        ),
    )

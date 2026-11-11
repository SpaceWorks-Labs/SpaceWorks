"""Parity O-B1: member units (districts, chapters, branches) and unit-scoped staff.

* `membership.units` -- the unit tree, member and plan assignment, the join-form unit picker and per-unit
  payment instructions. OFF by default; the data is kept when it is switched off.
* `membership.unit_scoped_staff` -- narrow one staff member's member-facing authority to a unit and the
  units beneath it. Needs `membership.units`. OFF by default; switching it off lifts every narrowing.
"""


def definitions(feature):
    from .capability_definitions_r3_org_money import definitions as money_definitions  # parity O-B3, chained here

    from .capability_definitions_r3_org_b2 import definitions as join_funnel_definitions  # parity O-B2

    return money_definitions(feature) + join_funnel_definitions(feature) + (
        feature("membership.units", "membership", "Member units",
                "Group members into districts, chapters or branches inside this space, up to four named levels. "
                "Plans can be limited to units and each unit can carry its own payment instructions."),
        feature("membership.unit_scoped_staff", "membership", "Unit-scoped staff",
                "Limit a staff member to the members of one unit and the units beneath it.",
                requires_features=("membership.units",)),
    )

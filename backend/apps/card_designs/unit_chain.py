"""A member's unit chain for cards (O-B4 part 2, parity C17): the unit and its ancestors, outermost first.

Read live (never copied onto the card), so moving a member to another unit changes the printed unit on the
next render. Empty while the space has `membership.units` off or the member has no unit.
"""
from apps.makerspaces.membership_features import membership_feature_on
from apps.makerspaces.models_member_units import MembershipUnit


def chain(membership):
    """-> list of MemberUnit, outermost first (at most four)."""
    if membership is None or not membership_feature_on(membership.makerspace, "units"):
        return []
    row = MembershipUnit.objects.filter(membership=membership).select_related("unit").first()
    units, unit = [], row.unit if row else None
    while unit is not None and len(units) < 4:
        units.insert(0, unit)
        unit = unit.parent
    return units


def codes(membership):
    return tuple(unit.code for unit in chain(membership))


def values(membership):
    """The data-field values: `unit`, `unit_code`, `units` (names joined by " / "), `level1`..`level4`."""
    units = chain(membership)
    result = {"unit": units[-1].name if units else "", "unit_code": units[-1].code if units else "",
              "units": " / ".join(unit.name for unit in units)}
    for index in range(4):
        result[f"level{index + 1}"] = units[index].name if index < len(units) else ""
    return result

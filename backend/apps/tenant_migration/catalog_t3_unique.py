"""Uniqueness constraints that carry no makerspace column but are owned through remapped parents (final 0.12.0 round).

Each follows the imported parent rows (event, series, organization, ticket type, plan, unit, membership), whose ids
remap on the target, so a pair that was unique on the source stays unique there.
"""

_FOLLOW = "Unique per remapped parent; follows the imported parents."
_CONSTRAINTS = (
    ("card_designs.CardDesign", "uniq_card_design_event_role"),
    ("card_designs.CardDesign", "uniq_card_design_org_role"),
    ("card_designs.CardDesign", "uniq_card_design_ticket_type_role"),
    ("events.EventInvite", "event_invite_series_unique_code"),
    ("makerspaces.ImportedMemberUnit", "field:imported"),
    ("makerspaces.MembershipRequestUnit", "field:request"),
    ("makerspaces.MembershipUnit", "field:membership"),
    ("makerspaces.PlanUnit", "uniq_plan_unit"),
    ("makerspaces.StaffUnitScope", "field:membership"),
)


def unique_rules(remap, policy):
    return {key: policy(remap, _FOLLOW) for key in _CONSTRAINTS}

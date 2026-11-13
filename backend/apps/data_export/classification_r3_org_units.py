"""Parity O-B1 (member units): literal export classification.

Units, their assignments and a plan's unit limits are the space's own organisation of its members and travel with it.
A unit's `path` is built from CODES (unique per space, immutable once a unit has children or members), so it carries
no source ids and needs no remapping. The staff unit scope and a member's unit reference `MakerspaceMembership`
(the person is the membership's data subject through that row); none of these tables adds an `accounts.User` FK.
"""
from .types import TenantPredicate as P

FIELDS = {
    "makerspaces.MemberUnitSettings": "id makerspace level_names updated_at",
    "makerspaces.MemberUnit": "id makerspace parent name slug code level path sort_order payment_instructions "
                              "archived_at created_at updated_at",
    "makerspaces.MembershipUnit": "id makerspace membership unit assigned_at",
    "makerspaces.StaffUnitScope": "id makerspace membership unit updated_at",
    "makerspaces.PlanUnit": "id makerspace plan unit",
    "makerspaces.MembershipRequestUnit": "id makerspace request unit",
    "makerspaces.ImportedMemberUnit": "id makerspace imported unit review_status reviewed_at",
}
DATASETS = {
    "makerspaces.MemberUnitSettings": ("members/member_unit_settings.csv", P(("makerspace",))),
    "makerspaces.MemberUnit": ("members/member_units.csv", P(("makerspace",))),
    "makerspaces.MembershipUnit": ("members/membership_units.csv", P(("makerspace",))),
    "makerspaces.StaffUnitScope": ("members/staff_unit_scopes.csv", P(("makerspace",))),
    "makerspaces.PlanUnit": ("members/plan_units.csv", P(("makerspace",))),
    "makerspaces.MembershipRequestUnit": ("members/membership_request_units.csv", P(("makerspace",))),
    "makerspaces.ImportedMemberUnit": ("members/imported_member_units.csv", P(("makerspace",))),
}
# Level names are plain labels.
NON_REFERENCE_JSON_FIELDS = frozenset({("makerspaces.MemberUnitSettings", "level_names")})

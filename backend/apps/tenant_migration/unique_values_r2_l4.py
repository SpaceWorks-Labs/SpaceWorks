"""Deployment-global uniqueness for lane L4's membership lifecycle rows.

Each rule is keyed on a membership (or its invitation), which the importer remaps to the
target allocation, so the remapped reference keeps the tuple unique; a duplicate refuses.
"""

from .unique_values_policy import REMAP, _policy

_REMAP = "Keyed on a remapped membership reference; duplicate tuples refuse."

RULES = {
    ("makerspaces.ImportedMember", "field:invitation"): _policy(
        REMAP, "The one-to-one invitation follows its imported request identity."),
    ("makerspaces.MembershipConsent", "uniq_membership_consent_open_purpose"): _policy(REMAP, _REMAP),
    ("makerspaces.MembershipErasureRequest", "uniq_membership_open_erasure"): _policy(REMAP, _REMAP),
    ("makerspaces.MembershipRecord", "field:membership"): _policy(
        REMAP, "One record per membership: the remapped membership keeps it unique."),
    ("makerspaces.MembershipTitleAssignment", "uniq_membership_primary_title"): _policy(REMAP, _REMAP),
    ("makerspaces.MembershipTitleAssignment", "uniq_membership_title_assignment"): _policy(REMAP, _REMAP),
}

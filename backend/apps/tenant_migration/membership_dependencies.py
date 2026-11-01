"""Literal classification of rows that cannot survive without a membership."""

from dataclasses import dataclass


@dataclass(frozen=True)
class MembershipDependency:
    retained_by_import: bool
    reason: str

MEMBERSHIP_DEPENDENT_MODELS = {
    "accounts.MemberClaimCode": MembershipDependency(
        retained_by_import=False,
        reason="Transient claim credentials are omitted from tenant archives.",
    ),
    "events.MemberCalendarFeed": MembershipDependency(
        retained_by_import=False,
        reason=(
            "A deployment-local bearer credential over the member's registration history. "
            "It is already omitted from tenant archives, so a restored tenant reissues it "
            "rather than carrying a live subscribable token across deployments."
        ),
    ),
    "makerspaces.MemberProfile": MembershipDependency(
        retained_by_import=True,
        reason="A member profile is owned by one non-null makerspace membership.",
    ),
    "makerspaces.MembershipTerm": MembershipDependency(
        retained_by_import=True,
        reason="A term records what one membership was sold and when; it travels with the membership.",
    ),
    "machines.CertificationGrant": MembershipDependency(
        retained_by_import=True,
        reason="A certification grant records that one membership was trained; it travels with the membership.",
    ),
    "makerspaces.MembershipAdditionalRole": MembershipDependency(
        retained_by_import=False,
        reason="Staff authority is dropped on import; every imported membership becomes Member.",
    ),
    "machines.MembershipMachineTypeScope": MembershipDependency(
        retained_by_import=False,
        reason="A Machine Manager's per-person type reach is authority and is dropped on import.",
    ),
    # Release 2 L4: membership lifecycle rows are exported with the space and travel with
    # their membership.
    "makerspaces.MembershipConsent": MembershipDependency(
        retained_by_import=True,
        reason="The consent ledger records what one membership agreed to; it travels with the membership.",
    ),
    "makerspaces.MembershipErasureRequest": MembershipDependency(
        retained_by_import=True,
        reason="An erasure request is one membership's privacy history; it travels with the membership.",
    ),
    "makerspaces.MembershipRecord": MembershipDependency(
        retained_by_import=True,
        reason="A membership's record fields belong to that membership; they travel with it.",
    ),
    "makerspaces.MembershipTermStatusEvent": MembershipDependency(
        retained_by_import=True,
        reason="Append-only term history of one membership; it travels with the membership.",
    ),
    "makerspaces.MembershipTitleAssignment": MembershipDependency(
        retained_by_import=True,
        reason="A title held by one membership; it travels with the membership.",
    ),
}

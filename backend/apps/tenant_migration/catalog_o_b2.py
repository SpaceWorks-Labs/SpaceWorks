"""Parity O-B2: tenant-dump field snapshot for the join-request change bookkeeping and plan join toggles.

Closed enums, workflow timestamps and a staff note to the applicant; none selects target authority. An open
`changes_requested` request is dropped on import like every other open admission state (target_projection_rows).
"""

EXTRA_FIELDS = {
    "makerspaces.MembershipRequest": frozenset({"changes_note", "changes_requested_at", "changes_rounds"}),
    "makerspaces.MembershipPlan": frozenset({"join_photo", "join_phone", "join_state"}),
}

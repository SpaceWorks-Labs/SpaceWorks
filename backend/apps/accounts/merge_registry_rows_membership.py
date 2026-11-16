"""Account-merge dispositions for the L4 membership lifecycle models (release 2)."""

from .merge_registry_types import KEEP_ON_SHELL as K, REPOINT as R, UNIQUE_RESOLVE as U

ROWS = (
    (K, "makerspaces.MembershipTermStatusEvent", "actor", "Append-only term history; actor_ids_for follows the alias."),
    (R, "makerspaces.MembershipRecord", "updated_by", "Mutable ownership or attribution; moves to the survivor."),
    (R, "makerspaces.MembershipTitleAssignment", "assigned_by", "Mutable ownership or attribution; moves to the survivor."),
    (R, "makerspaces.MembershipErasureRequest", "decided_by", "Mutable ownership or attribution; moves to the survivor."),
    (R, "makerspaces.MembershipImportBatch", "created_by", "Mutable ownership or attribution; moves to the survivor."),
    (R, "makerspaces.ImportedMember", "created_by", "Mutable ownership or attribution; moves to the survivor."),
    (U, "makerspaces.MembershipSummaryOptOut", "user",
     "One opt-out per person and space; survivor wins, the loser stays on the shell."),
    (R, "makerspaces.MembershipInviteLink", "created_by", "Mutable ownership or attribution; moves to the survivor."),
)

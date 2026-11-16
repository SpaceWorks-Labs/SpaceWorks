"""Audit metadata IDs written by release-2 lane r2-superadmin-controls (#185, #187A).

Every one names a platform or account row a tenant dump does not carry (a hosting plan, a hosting
request, a staff invitation, an account), so each travels as the source's local snapshot.
"""

from .audit_references_targets import AuditReference, AuditReferenceDisposition

S = AuditReferenceDisposition.SOURCE_LOCAL_SNAPSHOT

EDGES = {
    ("managed_hosting.plan_assigned", "plan_id"): AuditReference(S, "managed_hosting.HostingPlan"),
    ("managed_hosting.trial_expired", "plan_id"): AuditReference(S, "managed_hosting.HostingPlan"),
    ("space_control.ownership_invited", "invitation_id"): AuditReference(S, "accounts.StaffInvitation"),
    ("space_control.ownership_transferred", "new_user_id"): AuditReference(S, "accounts.User"),
    ("space_control.ownership_transferred", "previous_user_id"): AuditReference(S, "accounts.User"),
    ("space_control.space_onboarded", "hosting_request_id"): AuditReference(S, "hosting_requests.HostingRequest"),
    # A platform row (makerspace=None) written after the space it names was purged.
    ("space_control.scheduled_purge_ran", "makerspace_id"): AuditReference(S, "makerspaces.Makerspace"),
}

"""Release-2 lane L4 audit meta ids (membership lifecycle).

Ids of rows that travel in a tenant dump are remapped to the target's ids; the invite
link (deployment-local, never in a dump), a user id in summary opt-outs and the
refund-case id are kept as inert source provenance.
"""
from .audit_references_targets import AuditReference, AuditReferenceDisposition

R = AuditReferenceDisposition.REMAP
_S = AuditReference(AuditReferenceDisposition.SOURCE_LOCAL_SNAPSHOT, None, "programme_source_provenance")
MEMBERSHIP, TERM = "makerspaces.MakerspaceMembership", "makerspaces.MembershipTerm"


def _remap(model, *edges):
    return {edge: AuditReference(R, model) for edge in edges}


_MEMBER_ACTIONS = (
    "membership.term_status_changed", "membership.extended", "membership.renewal_reminder_sent",
    "membership.record_updated", "membership.title_assigned", "membership.title_unassigned",
    "membership.consent_given", "membership.consent_withdrawn", "membership.erasure_requested",
    "membership.erasure_withdrawn", "membership.erasure_approved", "membership.erasure_rejected",
    "membership.import_accepted",
)
_TERM_ACTIONS = ("membership.term_status_changed", "membership.extended", "membership.renewal_reminder_sent",
                 "membership.import_accepted", "payment.refund_case_term_ended")
_TITLE_ACTIONS = ("membership.title_created", "membership.title_updated", "membership.title_archived",
                  "membership.title_restored", "membership.title_assigned", "membership.title_unassigned")
_ERASURE_ACTIONS = ("membership.erasure_requested", "membership.erasure_withdrawn", "membership.erasure_approved",
                    "membership.erasure_rejected")

EDGES = {
    **_remap(MEMBERSHIP, *((action, "membership_id") for action in _MEMBER_ACTIONS)),
    **_remap(TERM, *((action, "term_id") for action in _TERM_ACTIONS)),
    **_remap("makerspaces.MembershipTermStatusEvent", ("membership.term_status_changed", "event_id")),
    **_remap("makerspaces.MembershipTitle", *((action, "title_id") for action in _TITLE_ACTIONS)),
    **_remap("makerspaces.MembershipConsent", ("membership.consent_given", "consent_id"),
             ("membership.consent_withdrawn", "consent_id")),
    **_remap("makerspaces.MembershipErasureRequest", *((action, "request_id") for action in _ERASURE_ACTIONS)),
    **_remap("makerspaces.MembershipPlan", ("membership.plan_archived", "plan_id"),
             ("membership.plan_restored", "plan_id")),
    **_remap("makerspaces.MembershipImportBatch", ("membership.imported", "batch_id")),
    **_remap("makerspaces.ImportedMember", ("membership.import_accepted", "imported_member_id"),
             ("membership.invited", "imported_member_id")),
    **_remap("makerspaces.MembershipRequest", ("membership.bulk_decided", "request_ids")),
    **_remap("payments.Payment", ("payment.refund_case_term_ended", "payment_id")),
    ("payment.refund_case_term_ended", "case_id"): _S,
    ("membership.invite_link_created", "link_id"): _S,
    ("membership.invite_link_created", "plan_id"): AuditReference(R, "makerspaces.MembershipPlan"),
    ("membership.invite_link_revoked", "link_id"): _S,
    ("membership.invite_link_redeemed", "link_id"): _S,
    ("membership.summary_opted_out", "user_id"): _S,
    ("membership.summary_opted_in", "user_id"): _S,
}

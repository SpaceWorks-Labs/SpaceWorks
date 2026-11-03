"""Audit metadata IDs written by release-2 lane L3 (ID cards).

`card.*` rows can name any of the three holder kinds, so their `card_id` is nulled with
provenance rather than remapped to one model. Jobs and wallet passes are omitted models.
"""

from .audit_references_targets import AuditReference, AuditReferenceDisposition

R, N = AuditReferenceDisposition.REMAP, AuditReferenceDisposition.NULL


def _remap(model, *edges):
    return {edge: AuditReference(R, model) for edge in edges}


def _null(kind, *edges):
    return {edge: AuditReference(N, None, kind) for edge in edges}


_DESIGN_ACTIONS = ("created", "saved", "published", "submitted", "approved", "rejected", "reset", "deleted",
                   "exported", "imported")
_EVENT_DESIGN = ("saved", "published", "submitted", "approved", "rejected")

EDGES = {
    **_remap("card_designs.CardDesign", *((f"card_design.{action}", "design_id") for action in _DESIGN_ACTIONS)),
    **_remap("card_designs.CardDesignApproval", *((f"card_design.{action}", "approval_id")
                                                  for action in ("submitted", "approved", "rejected"))),
    **_remap("events.Event", *((f"card_design.{action}", "event_id") for action in _EVENT_DESIGN),
             ("event_card.issued", "event_id"), ("event_card.revoked", "event_id"),
             ("event_card.role_changed", "event_id"), ("event_card.extras_access_changed", "event_id"),
             ("event_card.extras_viewed", "event_id"), ("card.scanned_for_checkin", "event_id")),
    **_remap("id_programmes.IdProgramme", *((f"card_design.{action}", "programme_id") for action in _EVENT_DESIGN),
             *((f"id_programme.{action}", "programme_id") for action in (
                 "created", "updated", "fields_updated", "closed", "deleted", "card_requested", "card_added",
                 "card_deleted", "card_linked", "cards_approved", "cards_rejected", "cards_revoked",
                 "cards_reinstated", "cards_renewed", "cards_imported"))),
    **_remap("organizations.Organization", *((f"card_design.{action}", "acted_for_organization_id")
                                             for action in ("saved", "published"))),
    **_remap("makerspaces.MemberCard", *((f"member_card.{action}", "card_id")
                                         for action in ("auto_issued", "downloaded", "emailed"))),
    **_remap("id_programmes.IdProgrammeCard", *((f"id_programme.{action}", "card_id") for action in (
        "card_requested", "card_added", "card_updated", "card_deleted", "card_linked", "card_photo_updated",
        "card_photo_removed", "card_downloaded", "card_emailed"))),
    **_remap("id_programmes.IdProgrammeImport", ("id_programme.cards_imported", "import_id")),
    **_remap("events.EventIdCard", *((f"event_card.{action}", "card_id") for action in (
        "issued", "revoked", "role_changed", "downloaded", "emailed", "photo_updated", "photo_removed"))),
    **_remap("events.EventRegistration", ("event_card.issued", "registration_id"),
             ("card.scanned_for_checkin", "registration_id")),
    **_remap("presence.PresenceSession", ("card.scanned_for_checkin", "session_id")),
    **_remap("card_designs.CardPhotoRequest", ("card.photo_requested", "request_id")),
    **_null("audit_polymorphic_card", *((f"card.{action}", "card_id") for action in (
        "extras_optin_changed", "photo_requested", "photo_cleanup_accepted", "verify_optin_changed",
        "verify_link_rotated"))),
    **_null("audit_omitted_target_model", *((f"card_job.{action}", "job_id") for action in (
        "queued", "succeeded", "failed", "cancelled", "result_downloaded")), ("card.photo_cleanup_accepted", "job_id"),
        *((f"wallet_pass.{action}", "pass_id") for action in ("issued", "updated", "voided"))),
}

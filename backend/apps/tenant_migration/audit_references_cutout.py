"""Decision 314(c) audit meta ids. Cut-outs and photo batches are omitted (derived / temporary) models, and the card id
can name any holder kind, so those ids are nulled with provenance; an event id remaps with the event."""
from .audit_references_targets import AuditReference, AuditReferenceDisposition

R, N = AuditReferenceDisposition.REMAP, AuditReferenceDisposition.NULL
_CUTOUT = ("requested", "done", "failed", "choice", "discarded")
_BATCH = ("created", "applied", "item_applied", "finished", "cancelled")

EDGES = {
    **{(f"card.photo_cutout_{action}", "card_id"): AuditReference(N, None, "audit_polymorphic_card")
       for action in _CUTOUT},
    **{(f"card.photo_cutout_{action}", "cutout_id"): AuditReference(N, None, "audit_omitted_target_model")
       for action in _CUTOUT},
    **{(f"card_photo_batch.{action}", "batch_id"): AuditReference(N, None, "audit_omitted_target_model")
       for action in _BATCH},
    ("card_photo_batch.item_applied", "item_id"): AuditReference(N, None, "audit_omitted_target_model"),
    ("card_photo_batch.item_applied", "card_id"): AuditReference(N, None, "audit_polymorphic_card"),
    ("card_photo_batch.created", "event_id"): AuditReference(R, "events.Event"),
    **{(f"card.photo_eraser_{action}", "card_id"): AuditReference(N, None, "audit_polymorphic_card")
       for action in ("opted_out", "opted_in")},
}

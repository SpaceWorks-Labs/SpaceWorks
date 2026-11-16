"""Card Studio audit meta ids: templates travel with the space (their ids remap); the design id remaps with the design."""
from .audit_references_targets import AuditReference, AuditReferenceDisposition

R = AuditReferenceDisposition.REMAP
_TEMPLATE_ACTIONS = ("created", "imported", "updated", "deleted")

EDGES = {
    **{(f"card_template.{action}", "template_id"): AuditReference(R, "card_designs.CardTemplate")
       for action in _TEMPLATE_ACTIONS},
    **{(f"card_template.{action}", "design_id"): AuditReference(R, "card_designs.CardDesign")
       for action in ("created", "imported")},
    ("card_design.template_applied", "design_id"): AuditReference(R, "card_designs.CardDesign"),
    ("card_design.csv_merged", "design_id"): AuditReference(R, "card_designs.CardDesign"),
    # A deleted library asset: its id names a row that no longer exists anywhere.
    ("card_design.asset_deleted", "asset_id"): AuditReference(AuditReferenceDisposition.NULL, None, "audit_omitted_target_model"),
}

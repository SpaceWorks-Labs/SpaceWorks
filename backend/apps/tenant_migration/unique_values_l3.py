"""Deployment-global uniqueness for lane L3's rows (ID cards).

Overrides and per-holder rows are unique per remapped parent, so they follow it. Design
asset ids are preserved (documents reference them) and regenerated only on a
collision; their object keys are rewritten by the private-object import. A programme
slug is unique within its organisation, and its card numbers within the programme.
"""

from .unique_value_generators import _refuses_collision
from .unique_values_policy import PRESERVE, REMAP, _policy


@_refuses_collision
def _refuse_asset_collision(row, target, source_value):
    raise RuntimeError("A card design asset id already exists on the target; design documents reference it.")


_FOLLOW = "Unique per remapped parent row; follows the imported parent."

RULES = {
    **{("card_designs.CardDesign", name): _policy(REMAP, _FOLLOW) for name in (
        "uniq_card_design_programme", "uniq_card_design_org_default", "uniq_card_design_event",
        "uniq_card_design_ticket_type")},
    ("card_designs.CardDesignAsset", "field:asset_id"): _policy(
        PRESERVE, "Design documents reference the asset id; kept unless another space already holds it.",
        field="asset_id", generator=_refuse_asset_collision),
    ("card_designs.CardDesignAsset", "field:object_key"): _policy(
        REMAP, "The verified private-object import allocates target keys."),
    ("card_designs.CardApprovalSetting", "uniq_card_approval_programme"): _policy(REMAP, _FOLLOW),
    ("card_designs.CardApprovalSetting", "uniq_card_approval_event"): _policy(REMAP, _FOLLOW),
    **{("card_designs.CardPhotoRequest", f"uniq_open_photo_request_{field}"): _policy(REMAP, _FOLLOW)
       for field in ("member_card", "programme_card", "event_card")},
    ("id_programmes.IdProgramme", "uniq_id_programme_slug"): _policy(
        REMAP, "A programme slug is unique within its organisation; follows the remapped organisation."),
    **{("id_programmes.IdProgrammeCard", name): _policy(REMAP, _FOLLOW) for name in (
        "uniq_id_programme_card_email", "uniq_id_programme_card_number", "uniq_id_programme_card_user")},
    ("events.EventIdCard", "uniq_live_event_id_card"): _policy(REMAP, _FOLLOW),
}

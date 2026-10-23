"""Audit metadata IDs written by release-2 lane L12 (consumables, loans, machines depth)."""

from .audit_references_targets import AuditReference, AuditReferenceDisposition

R = AuditReferenceDisposition.REMAP


def _remap(model, *edges):
    return {edge: AuditReference(R, model) for edge in edges}


EDGES = {
    **_remap("procurement.ToBuyItem", ("procurement.auto_tobuy_created", "to_buy_item_id"),
             ("procurement.consumable_refilled", "item_id")),
    **_remap("inventory.InventoryProduct", ("procurement.auto_tobuy_created", "product_id")),
    **_remap("machines.MachineConsumable", ("procurement.auto_tobuy_created", "consumable_id"),
             ("procurement.consumable_refilled", "consumable_id")),
}

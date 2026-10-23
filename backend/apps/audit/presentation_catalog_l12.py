"""Presentation entries: release-2 lane L12 (consumables, loans depth, machines depth).

``permitted`` lists only reviewed non-personal leaf paths (ids, counts, statuses)."""

from .presentation_catalog_types import P

ENTRIES = (
    P("procurement.auto_tobuy_created", "Automatic To-Buy created",
      ("to_buy_item_id", "product_id", "consumable_id", "available", "reorder_point", "remaining", "threshold")),
    P("procurement.consumable_refilled", "Machine consumable refilled from To-Buy",
      ("item_id", "consumable_id", "amount", "remaining")),
)

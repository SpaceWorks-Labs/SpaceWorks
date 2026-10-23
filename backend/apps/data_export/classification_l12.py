"""Release-2 lane L12 (machines and loans depth): reviewed fields and models."""

EXPORTED_FIELDS = {}
FIELD_ADDITIONS = {
    "inventory.InventoryProduct": "is_consumable",
    "procurement.ToBuyItem": "source_consumable",
}
OMITTED_MODELS = {}

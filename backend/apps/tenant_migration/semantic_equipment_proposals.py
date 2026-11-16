"""Remap the typed product references in immutable equipment-kit snapshots.

The caller supplies the existing archive PK-map lookup; unknown or malformed
references refuse the import instead of retaining source-local identifiers.
"""
from .insertion_errors import ArchiveFormatError

_MODELS = frozenset({
    "inventory.EquipmentKitVersion",
    "inventory.EquipmentConsumablePlan",
    "inventory.EquipmentKitAllocation",
})


def remap(label, source, row, map_id):
    if label not in _MODELS:
        return False
    lines = row.get("lines")
    if not isinstance(lines, list) or not 1 <= len(lines) <= 50:
        raise ArchiveFormatError("Invalid equipment kit snapshot lines.")
    result = []
    seen = set()
    targets = set()
    for line in lines:
        if not isinstance(line, dict) or set(line) != {"product_id", "quantity_per_person", "kind"}:
            raise ArchiveFormatError("Invalid equipment kit snapshot line.")
        product, quantity, kind = line["product_id"], line["quantity_per_person"], line["kind"]
        if (type(product) is not int or product <= 0 or product in seen
                or type(quantity) is not int or not 1 <= quantity <= 99
                or not isinstance(kind, str) or kind not in {"returnable", "consumable"}):
            raise ArchiveFormatError("Invalid equipment kit snapshot line.")
        seen.add(product)
        target = map_id("inventory.InventoryProduct", product)
        if type(target) is not int or target <= 0 or target in targets:
            raise ArchiveFormatError("Invalid mapped equipment product.")
        targets.add(target)
        result.append({"product_id": target, "quantity_per_person": quantity, "kind": kind})
    row["lines"] = result
    return True

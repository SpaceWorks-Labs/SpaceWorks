"""Image references of a certificate design, for v2 layouts and Studio (v3) documents alike (library capture, clone)."""


def image_ids(document):
    """Event artwork resource ids a design prints: v2 `image` layers, or every v3 asset id (layers, backgrounds, watermark)."""
    if (document or {}).get("version") == 3:
        from apps.card_designs.layout import asset_ids
        return set(asset_ids(document))
    return {row["resource_id"] for row in (document or {}).get("layers", []) if row["type"] == "image"}


def remap(document, mapping):
    """Replace artwork ids in place with `mapping` (old -> new). Signatory slots are untouched: a copy never carries
    another event's signatories or approvals, the copy is approved afresh when it is saved."""
    if document.get("version") == 3:
        mark = document.get("watermark") or {}
        if mark.get("asset_id") in mapping:
            mark["asset_id"] = mapping[mark["asset_id"]]
        for side in ("front", "back"):
            background = (document.get(side) or {}).get("background") or {}
            if background.get("kind") == "image":
                background["asset_id"] = mapping[background["asset_id"]]
            for layer in (document.get(side) or {}).get("layers", []):
                if layer["kind"] == "image":
                    layer["asset_id"] = mapping[layer["asset_id"]]
        return document
    for layer in document.get("layers", []):
        if layer["type"] == "image":
            layer["resource_id"] = mapping[layer["resource_id"]]
    return document

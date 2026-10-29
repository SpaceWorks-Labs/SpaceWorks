"""The in-browser preview a stored maker file offers; the registry is the one source of truth.

The browser admits a preview by this kind (never by its own extension list). KiCad previews sit
behind the `events.kicad_preview` capability: when it is off the file is download-only, exactly
like every other unpreviewed maker format.
"""
from apps.maker_formats.registry import REGISTRY
from apps.makerspaces.platform import feature_enabled

KINDS = ("download", "image", "pdf", "mesh", "brep", "gerber", "kicad", "text", "table", "video", "listing")
GATED = {"kicad": "events.kicad_preview"}


def asset_preview(asset):
    """Return (kind, preview_max_bytes) for one asset row."""
    spec = REGISTRY.get((asset.extension, asset.subtype))
    if spec is None:
        return "download", None
    feature = GATED.get(spec.preview)
    if feature and not feature_enabled(asset.event.makerspace, feature):
        return "download", None
    return spec.preview, spec.preview_max_bytes

"""Where a card face's file is on THIS server: bundled, or fetched and cached locally.

Rendering never fetches from the network: a catalogue face that is not READY yet
returns None and the text falls back to the bundled Noto chain.
"""
import hashlib
import logging
import os
import tempfile
from pathlib import Path

from django.conf import settings

from .fonts import bundled_path, slug

logger = logging.getLogger(__name__)


def cache_dir():
    root = Path(getattr(settings, "CARD_FONT_CACHE_DIR", "") or Path(tempfile.gettempdir()) / "spaceworks-card-fonts")
    root.mkdir(parents=True, exist_ok=True)
    return root


def object_key(family, weight):
    return f"card-fonts/{slug(family)}/{int(weight)}.ttf"


def local_path(family, weight):
    path = bundled_path(family, weight)
    if path is not None:
        return Path(path)
    from .models import CardFont
    row = CardFont.objects.filter(family=family, weight=weight, state=CardFont.State.READY).first()
    if row is None:
        return None
    target = cache_dir() / f"{slug(family)}-{int(weight)}-{row.sha256[:12]}.ttf"
    if target.exists():
        return target
    from .storage import read_optional
    data = read_optional(row.font_key)
    if not data or hashlib.sha256(data).hexdigest() != row.sha256:
        logger.warning("card_font_cache_mismatch", extra={"family": family, "weight": weight})
        return None
    partial = target.with_suffix(".part")
    partial.write_bytes(data)
    os.replace(partial, target)
    return target


def font_bytes(family, weight):
    """Bytes for the designer's FontFace loader; None when not available yet."""
    path = local_path(family, weight)
    if path is None:
        return None
    return Path(path).read_bytes()

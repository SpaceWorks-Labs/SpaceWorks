"""The card font library (#128 C-21, Q-I2): the full Google Fonts catalogue, self-hosted.

Three sources, in order of preference for a (family, weight):

1. Bundled brand faces -- Gilroy 400-700 and Unbounded 400-700 -- shipped in the image.
2. Bundled Noto faces the image already carries for print fallback (Latin, Indic,
   Arabic, Hebrew, CJK), Regular and Bold.
3. Every other family in `font_catalog.json` (the open Google Fonts catalogue). Its
   files are fetched SERVER-SIDE on first use (`font_fetch.py`, a Celery task), kept in
   private object storage, and served to the designer by this app. The browser never
   calls Google; the renderer never fetches at render time and falls back to Noto
   until a family is ready.

Staff chrome stays Gilroy/Unbounded; these families exist only inside card designs.
"""
import json
import re
from functools import lru_cache
from pathlib import Path

BRAND_DIR = Path(__file__).resolve().parent.parent / "events" / "certificates" / "fonts"
BRAND = {
    "Gilroy": {400: "Gilroy-Regular.ttf", 500: "Gilroy-Medium.ttf", 600: "Gilroy-SemiBold.ttf", 700: "Gilroy-Bold.ttf"},
    "Unbounded": {weight: f"Unbounded-{weight}.ttf" for weight in (400, 500, 600, 700)},
}
CATEGORIES = ("sans", "serif", "display", "handwriting", "mono")
# The scripts the SPEC requires the library to cover, shown first in the script filter.
PRIORITY_SCRIPTS = ("latin", "malayalam", "devanagari", "tamil", "kannada", "telugu", "bengali",
                    "gujarati", "gurmukhi", "arabic")


def slug(family):
    return re.sub(r"[^a-z0-9]+", "-", family.lower()).strip("-")


@lru_cache(maxsize=1)
def catalogue():
    with open(Path(__file__).with_name("font_catalog.json"), encoding="utf-8") as handle:
        rows = json.load(handle)["families"]
    return {row[0]: {"family": row[0], "category": row[1], "weights": tuple(row[2]), "scripts": tuple(row[3]),
                     "popularity": row[4]} for row in rows}


@lru_cache(maxsize=1)
def bundled_noto():
    """Noto families the image ships, as {family: {weight: path}}."""
    try:
        from apps.operations.printable_fonts import font_paths
        paths = font_paths()
    except Exception:
        return {}
    found = {}
    for filename, path in paths.items():
        match = re.fullmatch(r"(Noto[A-Za-z]+)-(Regular|Bold)\.ttf", filename)
        if not match:
            continue
        family = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", match.group(1))
        found.setdefault(family, {})[400 if match.group(2) == "Regular" else 700] = path
    return found


def bundled_path(family, weight):
    if family in BRAND and weight in BRAND[family]:
        return BRAND_DIR / BRAND[family][weight]
    return bundled_noto().get(family, {}).get(weight)


def family_weights(family):
    """Every weight a design may choose for `family`; empty when it is not in the library."""
    if not isinstance(family, str):
        return ()
    weights = set(BRAND.get(family, {})) | set(bundled_noto().get(family, {}))
    weights |= set(catalogue().get(family, {}).get("weights", ()))
    return tuple(sorted(weights))


def is_bundled(family, weight):
    return bundled_path(family, weight) is not None


def describe(family):
    row = catalogue().get(family)
    if family in BRAND:
        return {"family": family, "category": "sans", "weights": family_weights(family),
                "scripts": ("latin", "latin-ext"), "popularity": 0, "bundled": True}
    if row is None and family in bundled_noto():
        return {"family": family, "category": "sans", "weights": family_weights(family),
                "scripts": (), "popularity": 0, "bundled": True}
    if row is None:
        return None
    return {**row, "weights": family_weights(family), "bundled": family in bundled_noto()}


def search(query="", *, category="", script="", limit=60, offset=0):
    """Brand faces first, then catalogue families by popularity."""
    query = (query or "").strip().lower()
    names = list(BRAND) + sorted(catalogue(), key=lambda name: (catalogue()[name]["popularity"] or 99999, name))
    rows = []
    for name in names:
        row = describe(name)
        if row is None or (query and query not in name.lower()):
            continue
        if category and row["category"] != category:
            continue
        if script and script not in row["scripts"]:
            continue
        rows.append(row)
    return len(rows), rows[offset:offset + limit]

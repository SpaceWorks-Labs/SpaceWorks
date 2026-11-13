"""Static print faces converted losslessly from the repository's approved WOFF2 kit.

The brand text face is Outfit (OFL). Designs stored before decision 220(c) name it
"Gilroy" (only Gilroy's free Light/ExtraBold may ship and ReportLab cannot embed the
CFF-outline ExtraBold, so that token always printed in Outfit); `LEGACY_FAMILIES` keeps
reading it as Outfit. See fonts/README.md.
"""

from functools import lru_cache
from pathlib import Path

BRAND_FAMILIES = ("Outfit", "Unbounded")
LEGACY_FAMILIES = {"Gilroy": "Outfit"}


def canonical(family):
    return LEGACY_FAMILIES.get(family, family)


@lru_cache(maxsize=8)
def face(family, weight):
    from fontTools.ttLib import TTFont as Font
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    filename = f"Outfit-{weight}.ttf" if canonical(family) == "Outfit" else f"Unbounded-{weight}.ttf"
    path = Path(__file__).with_suffix("") / filename
    name = "Event-" + path.stem
    if name not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont(name, str(path), shapable=True))
    with Font(path, lazy=True) as font:
        codes = frozenset((font.getBestCmap() or {}).keys())
    return name, codes


def runs(text, family, weight):
    from apps.operations.printable_fonts import clusters, font_runs, registered_name
    name, codes = face(family, weight)
    result = []
    for cluster in clusters(text):
        items = [(name, cluster)] if all(ord(char) in codes for char in cluster) else [
            (registered_name(filename), value) for filename, value in font_runs(cluster, "sans", weight >= 600)]
        for font, value in items:
            if result and result[-1][0] == font:
                result[-1] = (font, result[-1][1] + value)
            else:
                result.append((font, value))
    return result

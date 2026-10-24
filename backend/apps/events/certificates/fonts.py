"""Static print faces converted losslessly from the repository's approved WOFF2 kit."""

from functools import lru_cache
from pathlib import Path

WEIGHTS = {400: "Regular", 500: "Medium", 600: "SemiBold", 700: "Bold"}


@lru_cache(maxsize=8)
def face(family, weight):
    from fontTools.ttLib import TTFont as Font
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    filename = f"Gilroy-{WEIGHTS[weight]}.ttf" if family == "Gilroy" else f"Unbounded-{weight}.ttf"
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

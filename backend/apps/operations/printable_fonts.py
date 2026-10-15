"""Fixed font vocabulary, bundled in the backend image (Noto OFL fonts).

No user-selected paths or network font loading. Arabic uses explicit visual bidi;
Devanagari uses ReportLab/HarfBuzz shaping. CJK uses the PDF standard CID fallback.
"""

from functools import lru_cache
from itertools import groupby
from pathlib import Path
import unicodedata
from xml.sax.saxutils import escape


FONT_FAMILIES = {
    "sans": "NotoSans", "serif": "NotoSerif", "devanagari": "NotoSansDevanagari",
    "arabic": "NotoSansArabic", "hebrew": "NotoSansHebrew",
}
BUNDLED_FONT_ROOT = Path("/usr/local/share/spaceworks/fonts")


@lru_cache(maxsize=1)
def font_paths():
    """Resolve only the fixed font vocabulary, across supported image layouts.

    The image copies static Noto fonts to its own bundle, outside source mounts.
    Distribution paths also support older images and local development installs.
    Never replace a missing script font with Vera: that silently drops glyphs.
    """
    roots = (BUNDLED_FONT_ROOT, Path(__file__).parent / "fonts" / "noto",
             Path("/usr/share/fonts"), Path("/usr/local/share/fonts"))
    filenames = {f"{name}-{weight}.ttf" for name in FONT_FAMILIES.values()
                 for weight in ("Regular", "Bold")}
    found = {}
    for root in roots:
        if root.is_dir():
            for path in sorted(root.rglob("*.ttf")):
                if path.name in filenames:
                    found.setdefault(path.name, path)
    missing = sorted(filenames - found.keys())
    if missing:
        raise RuntimeError("Printable Noto font bundle missing: " + ", ".join(missing)
                           + ". Rebuild the backend image before running it.")
    return found


@lru_cache(maxsize=1)
def register_fonts():
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.cidfonts import UnicodeCIDFont
    from reportlab.pdfbase.ttfonts import TTFont

    paths = font_paths()
    for family, filename in FONT_FAMILIES.items():
        for bold, suffix in ((False, "Regular"), (True, "Bold")):
            path = paths[f"{filename}-{suffix}.ttf"]
            pdfmetrics.registerFont(TTFont(f"Print-{family}-{bold}", str(path), shapable=True))
    pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))


def script(character):
    code = ord(character)
    if 0x0900 <= code <= 0x097F:
        return "devanagari"
    if 0x0590 <= code <= 0x05FF:
        return "hebrew"
    if 0x0600 <= code <= 0x08FF or 0xFB50 <= code <= 0xFEFF:
        return "arabic"
    if 0x2E80 <= code <= 0xD7FF or 0xF900 <= code <= 0xFAFF:
        return "cjk"
    return None


def font_markup(text, family, bold):
    register_fonts()
    if any(unicodedata.bidirectional(c) in ("R", "AL") for c in text):
        from arabic_reshaper import reshape
        from bidi.algorithm import get_display
        text = get_display(reshape(text))
    runs = []
    for group, chars in groupby(text, key=lambda c: script(c) or family):
        font = "STSong-Light" if group == "cjk" else f"Print-{group}-{bold}"
        runs.append(f'<font name="{font}">{escape("".join(chars))}</font>')
    return "".join(runs)

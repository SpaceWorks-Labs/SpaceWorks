"""Fixed font vocabulary, bundled in the backend image (Debian Noto OFL fonts).

No user-selected paths or network font loading. Arabic uses explicit visual bidi;
Devanagari uses ReportLab/HarfBuzz shaping. CJK uses the PDF standard CID fallback.
"""

from functools import lru_cache
from itertools import groupby
from pathlib import Path
import unicodedata
from xml.sax.saxutils import escape


@lru_cache(maxsize=1)
def register_fonts():
    import reportlab
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.cidfonts import UnicodeCIDFont
    from reportlab.pdfbase.ttfonts import TTFont

    noto = Path("/usr/share/fonts/truetype/noto")
    vera = Path(reportlab.__file__).parent / "fonts"
    for family, filename in (("sans", "NotoSans"), ("serif", "NotoSerif"),
                              ("devanagari", "NotoSansDevanagari"),
                              ("arabic", "NotoSansArabic"), ("hebrew", "NotoSansHebrew")):
        for bold, suffix in ((False, "Regular"), (True, "Bold")):
            path = noto / f"{filename}-{suffix}.ttf"
            if not path.is_file():
                if family not in ("sans", "serif"):
                    raise RuntimeError("Printable Unicode fonts missing: rebuild the backend image.")
                path = vera / ("VeraBd.ttf" if bold else "Vera.ttf")
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

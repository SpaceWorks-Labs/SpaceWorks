"""Coverage-aware, cluster-safe fallback over the image's complete static Noto set."""

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
    roots = (BUNDLED_FONT_ROOT, Path(__file__).parent / "fonts" / "noto",
             Path("/usr/share/fonts"), Path("/usr/local/share/fonts"))
    found = {}
    for root in roots:
        if root.is_dir():
            for path in sorted(root.rglob("Noto*.ttf")):
                found.setdefault(path.name, path)
    required = {f"{name}-{weight}.ttf" for name in FONT_FAMILIES.values()
                for weight in ("Regular", "Bold")}
    required.update(f"NotoSans{region}-Regular.ttf" for region in ("SC", "TC", "JP", "KR"))
    missing = sorted(required - found.keys())
    if missing:
        raise RuntimeError("Printable Noto font bundle missing: " + ", ".join(missing)
                           + ". Rebuild the backend image before running it.")
    return found


@lru_cache(maxsize=None)
def font_cmap(filename):
    from fontTools.ttLib import TTFont
    with TTFont(font_paths()[filename], lazy=True) as font:
        if "glyf" not in font:
            raise RuntimeError(f"Printable font has no TrueType outlines: {filename}")
        return frozenset(code for code, glyph in (font.getBestCmap() or {}).items()
                         if font.getGlyphID(glyph) != 0)


@lru_cache(maxsize=16)
def fallback_chain(family="sans", bold=False):
    paths = font_paths()
    weight = "Bold" if bold else "Regular"
    preferred = f"{FONT_FAMILIES[family]}-{weight}.ttf"
    # Family preference first, then sans before serif and requested weight first.
    # Every bundled face remains reachable: no script-name whitelist drops a script.
    return tuple(sorted(paths, key=lambda name: (
        name != preferred, not name.endswith(f"-{weight}.ttf"),
        not name.startswith("NotoSans"), name)))


def clusters(text):
    import regex
    return regex.findall(r"\X", str(text))


def _visible_codes(text):
    # Joiners and variation selectors participate in shaping, never select a font
    # on their own. Keep them in the same run as their base character.
    return {ord(c) for c in text if unicodedata.category(c) != "Cf"
            and not 0xFE00 <= ord(c) <= 0xFE0F}


@lru_cache(maxsize=32768)
def select_font(cluster, family="sans", bold=False):
    chain = fallback_chain(family, bold)
    codes = _visible_codes(cluster)
    for filename in chain:
        if codes <= font_cmap(filename):
            return filename
    # Only genuinely uncovered characters get .notdef; never fail a whole PDF.
    return chain[0]


def font_runs(text, family="sans", bold=False):
    selected = []
    previous = fallback_chain(family, bold)[0]
    for cluster in clusters(text):
        filename = select_font(cluster, family, bold) if _visible_codes(cluster) else previous
        if not _visible_codes(cluster) <= font_cmap(filename):
            # An unusual cluster may combine characters from unrelated scripts.
            # Preserve normal shaping clusters; split only when no face covers one.
            for character in cluster:
                chosen = select_font(character, family, bold) if _visible_codes(character) else previous
                selected.append((chosen, character))
                previous = chosen
            continue
        selected.append((filename, cluster))
        previous = filename
    return [(filename, "".join(value for _, value in run))
            for filename, run in groupby(selected, key=lambda item: item[0])]


@lru_cache(maxsize=None)
def registered_name(filename):
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    for family, stem in FONT_FAMILIES.items():
        for bold, weight in ((False, "Regular"), (True, "Bold")):
            if filename == f"{stem}-{weight}.ttf":
                name = f"Print-{family}-{bold}"
                break
        else:
            continue
        break
    else:
        name = "Print-" + Path(filename).stem
    if name not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont(name, str(font_paths()[filename]), shapable=True))
    return name


@lru_cache(maxsize=1)
def register_fonts():
    for stem in FONT_FAMILIES.values():
        for weight in ("Regular", "Bold"):
            registered_name(f"{stem}-{weight}.ttf")


def font_markup(text, family, bold, *, logical=False):
    register_fonts()
    # Existing badge/pass layouts use visual bidi before ReportLab paragraph
    # wrapping. Billing uses logical text and per-font shaping in its flowable.
    if not logical and any(unicodedata.bidirectional(c) in ("R", "AL") for c in text):
        from arabic_reshaper import reshape
        from bidi.algorithm import get_display
        text = get_display(reshape(text))
    return "".join(f'<font name="{registered_name(filename)}">{escape(run)}</font>'
                   for filename, run in font_runs(text, family, bold))


def script(character):
    """Compatibility helper; font selection itself is exclusively cmap based."""
    code = ord(character)
    for start, end, name in ((0x0900, 0x097F, "devanagari"), (0x0590, 0x05FF, "hebrew"),
                             (0x0600, 0x08FF, "arabic"), (0x2E80, 0xD7FF, "cjk")):
        if start <= code <= end:
            return name
    return None

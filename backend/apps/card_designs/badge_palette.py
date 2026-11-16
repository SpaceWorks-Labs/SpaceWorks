"""Badge colours (E-B1): the Events palette rules, native.

Organisers pick brand colours; every text colour is contrast-checked (4.5:1) against what it sits on,
and Workshop Orange is only ever a fill. `event` means the event's accent: this release has no custom
accent colour (decision 294 excludes it), so it resolves to Maker Teal unless a caller passes one.
"""
from .contrast import ratio, rgb, to_hex

BRAND = {"ink": "#142C2A", "teal": "#006E63", "orange": "#FF7447", "citron": "#DFFF8F", "sky": "#B5CDFF",
         "yellow": "#FFD447", "cream": "#FFF4E8", "white": "#FFFFFF"}
MONO_INK = "#000000"
MINIMUM_CONTRAST = 4.5


def _contrast(first, second):
    return ratio(rgb(first), rgb(second))


def _colour(key, event_accent):
    return event_accent if key == "event" else BRAND[key]


def _mix(first, second, weight):
    a, b = rgb(first), rgb(second)
    return to_hex([x * weight + y * (1 - weight) for x, y in zip(a, b)])


def readable_on(surface, candidates):
    passing = next((c for c in candidates if _contrast(c, surface) >= MINIMUM_CONTRAST), None)
    return passing or max(candidates, key=lambda c: _contrast(c, surface))


def _is_readable(colour, surface):
    return colour.upper() != BRAND["orange"] and _contrast(colour, surface) >= MINIMUM_CONTRAST


def _band_safe(accent):
    if any(_contrast(text, accent) >= MINIMUM_CONTRAST for text in (BRAND["cream"], BRAND["ink"])):
        return accent
    for step in range(1, 21):
        deeper = _mix(BRAND["ink"], accent, step * 0.05)
        if _contrast(BRAND["cream"], deeper) >= MINIMUM_CONTRAST:
            return deeper
    return BRAND["ink"]


def resolve(settings, event_accent=None):
    """-> dict: background, text, heading, accent, on_accent, rule, tile, qr_light, symbol."""
    if settings["colorMode"] == "mono":
        return {"background": BRAND["white"], "text": MONO_INK, "heading": MONO_INK, "accent": MONO_INK,
                "on_accent": BRAND["white"], "rule": MONO_INK, "tile": BRAND["white"], "symbol": "ink"}
    accent_hex = (event_accent or BRAND["teal"]).upper()
    background = _band_safe(_colour(settings["backgroundColor"], accent_hex))
    accent = _band_safe(_colour(settings["accentColor"], accent_hex))
    automatic = readable_on(background, [BRAND["ink"], BRAND["cream"], BRAND["white"]])
    chosen = automatic if settings["textColor"] == "auto" else _colour(settings["textColor"], accent_hex)
    text = chosen if settings["textColor"] == "auto" or _is_readable(chosen, background) else automatic
    return {"background": background, "text": text,
            "heading": accent if _is_readable(accent, background) else text, "accent": accent,
            "on_accent": readable_on(accent, [BRAND["cream"], BRAND["ink"], BRAND["white"]]),
            "rule": accent if _contrast(accent, background) >= 1.5 else text, "tile": BRAND["white"],
            "symbol": "ink" if background == BRAND["white"] else "full"}

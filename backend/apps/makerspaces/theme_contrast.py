"""Accessible tenant brand tokens; keep in sync with lib/brandColours.ts.

Well-formed tenant colours stay accepted. Derived soft, link and interaction
colours degrade to safe defaults rather than narrowing the acceptance set.
"""

import re

INK, CREAM = (20, 44, 42), (255, 244, 232)
BLACK, WHITE = (0, 0, 0), (255, 255, 255)
SURFACES = {
    "light": ((255, 244, 232), (246, 236, 224), (255, 255, 255), (239, 230, 219)),
    "dark": ((20, 44, 42), (34, 56, 53), (48, 68, 65), (60, 78, 74)),
}
PRODUCT_FILL = {
    "light": (0, 110, 99),
    "dark": (0, 110, 99),
}
BODY_TEXT = {
    "light": ((20, 44, 42), (91, 104, 99)),
    "dark": ((255, 244, 232), (189, 188, 179)),
}
FIXED_INKS = {
    "light": ((0, 110, 99), (83, 109, 73), (105, 104, 52), (81, 105, 123), (185, 28, 28)),
    "dark": ((163, 196, 184), (223, 255, 143), (255, 212, 71), (181, 205, 255), (252, 165, 165)),
}
FIXED_SOFTS = {
    "light": ((224, 238, 236), (255, 238, 233), (251, 255, 242), (255, 250, 233), (246, 249, 255)),
    "dark": ((45, 71, 67), (60, 71, 65), (59, 79, 70), (60, 77, 65), (56, 76, 76)),
}


def rgb(value):
    if not isinstance(value, str) or not re.fullmatch(r"#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})", value):
        return None
    digits = value[1:]
    if len(digits) == 3:
        digits = "".join(channel * 2 for channel in digits)
    return tuple(int(digits[index:index + 2], 16) for index in (0, 2, 4))


def luminance(color):
    def linear(channel):
        value = channel / 255
        return value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4

    return sum(linear(channel) * weight for channel, weight in zip(color, (.2126, .7152, .0722)))


def contrast(a, b):
    high, low = sorted((luminance(a), luminance(b)), reverse=True)
    return (high + .05) / (low + .05)


def blend(a, b, amount, rounded=True):
    # Match JS Math.round, including half-channel ties.
    channels = tuple(x * (1 - amount) + y * amount for x, y in zip(a, b))
    return tuple(int(channel + .5) for channel in channels) if rounded else channels


def derive_palette(theme, mode):
    custom = bool(theme.get("primary_color") or theme.get("accent_color"))
    fill = rgb(theme.get("primary_color")) or PRODUCT_FILL[mode]
    foreground = next(color for color in (INK, CREAM, WHITE, BLACK) if contrast(color, fill) >= 4.5)
    away = INK if luminance(foreground) > .5 else CREAM
    toward = CREAM if away == INK else INK
    if contrast(blend(fill, away, .10), fill) < 1.06 and contrast(foreground, blend(fill, toward, .20)) >= 4.5:
        away = toward
    hover, active = blend(fill, away, .10), blend(fill, away, .20)
    # Preserve the old interaction derivation as the owner-approved fallback.
    fallback = WHITE if luminance(foreground) < .5 else BLACK
    if contrast(foreground, hover) < 4.5:
        hover = blend(fill, fallback, .08)
    if contrast(foreground, active) < 4.5:
        active = blend(fill, fallback, .16)
    surfaces, panel = SURFACES[mode], SURFACES[mode][2]
    texts = (*BODY_TEXT[mode], *FIXED_INKS[mode])
    soft = panel
    for step in range(101):
        candidate = blend(panel, fill, .12 * (1 - step / 100))
        if all(contrast(text, candidate) >= 4.55 for text in texts):
            soft = candidate
            break
    if not custom:
        soft = FIXED_SOFTS[mode][0]
    backgrounds = list(zip(("bg", "surface", "panel", "hover"), surfaces)) + [("brand-soft", soft)]
    backgrounds += list(zip(("accent-soft", "emphasis-soft", "success-soft", "warn-soft", "info-soft"), FIXED_SOFTS[mode]))
    ink = FIXED_INKS[mode][0]
    if custom:
        seed = rgb(theme.get("accent_color")) or fill
        endpoint = INK if mode == "light" else CREAM
        for step in range(101):
            candidate = blend(seed, endpoint, step / 100)
            if all(contrast(candidate, background) >= 4.5 for _, background in backgrounds):
                ink = candidate
                break
    pairs = [(f"on-brand on {name}", contrast(foreground, background), 4.5)
             for name, background in (("brand", fill), ("brand-hover", hover), ("brand-active", active))]
    pairs += [(f"brand-ink on {name}", contrast(ink, background), 4.5) for name, background in backgrounds]
    pairs += [(f"{name} on brand-soft", contrast(text, soft), 4.5)
              for name, text in zip(("ink", "muted", "accent-ink", "success-ink", "warn-ink", "info-ink", "danger"), texts)]
    pairs += [(f"brand boundary on {name}", contrast(ink, background), 3) for name, background in backgrounds[:3]]
    return {"fill": fill, "foreground": foreground, "hover": hover, "active": active, "soft": soft, "ink": ink, "pairs": pairs}


def contrast_failures(theme):
    return [{"mode": mode, "pair": pair, "ratio": ratio, "minimum": minimum}
            for mode in SURFACES for pair, ratio, minimum in derive_palette(theme, mode)["pairs"]
            if ratio < minimum]

"""Proposed tenant `brand` contract (replaces the `secondary` contract). Stdlib only.

python -I brand_contract.py tokens.json
"""
import json, sys
T = {m: {k: tuple(v) for k, v in d.items()} for m, d in json.load(open(sys.argv[1])).items()}

def lum(c):
    def ch(v):
        v /= 255
        return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4
    return sum(ch(v) * w for v, w in zip(c, (.2126, .7152, .0722)))
def contrast(a, b):
    hi, lo = sorted((lum(a), lum(b)), reverse=True)
    return (hi + .05) / (lo + .05)
def blend(a, b, t, rounded=True):
    ch = tuple(x * (1 - t) + y * t for x, y in zip(a, b))
    return tuple(int(c + .5) for c in ch) if rounded else ch
def rgb(v):
    d = v.lstrip("#"); d = "".join(c * 2 for c in d) if len(d) == 3 else d
    return tuple(int(d[i:i + 2], 16) for i in (0, 2, 4))

INK, CREAM = (20, 44, 42), (255, 244, 232)
BLACK, WHITE = (0, 0, 0), (255, 255, 255)
SURFACES = {m: (T[m]["bg"], T[m]["surface"], T[m]["panel"], T[m]["hover"]) for m in T}
BODY_TEXT = {m: (T[m]["ink"], T[m]["muted"]) for m in T}
FIXED_INKS = {m: tuple(T[m][k] for k in ("accent-ink", "success-ink", "warn-ink", "info-ink", "danger")) for m in T}
FIXED_SOFTS = {m: tuple(T[m][k + "-soft"] for k in ("accent", "emphasis", "success", "warn", "info")) for m in T}
PRODUCT_FILL = {m: T[m]["accent"] for m in T}
SOFT_REQUEST = .12

def foreground_for(fill):
    brand = max((INK, CREAM), key=lambda c: contrast(c, fill))
    if contrast(brand, fill) >= 4.5:
        return brand
    return max((INK, CREAM, WHITE), key=lambda c: contrast(c, fill))   # white = the only other brand neutral; may still fail -> rejected

def derive_palette(theme, mode):
    custom = bool(theme.get("primary_color") or theme.get("accent_color"))
    fill = rgb(theme["primary_color"]) if theme.get("primary_color") else PRODUCT_FILL[mode]
    fg = foreground_for(fill)
    away = INK if lum(fg) > .5 else CREAM          # interaction states move away from the label ...
    toward = CREAM if away == INK else INK         # ... unless that step is imperceptible AND the
    if contrast(blend(fill, away, .10), fill) < 1.06 and contrast(fg, blend(fill, toward, .20)) >= 4.5:
        away = toward                              # label keeps AA when we step toward it instead
    hover, active = blend(fill, away, .10), blend(fill, away, .20)
    surfaces, panel = SURFACES[mode], T[mode]["panel"]
    texts = (*BODY_TEXT[mode], *FIXED_INKS[mode])
    soft = panel
    for step in range(101):                         # strongest soft tint <= 12% keeping all text >= 4.55
        alpha = SOFT_REQUEST * (1 - step / 100)
        cand = blend(panel, fill, alpha)
        if all(contrast(t, cand) >= 4.55 for t in texts):
            soft = cand; break
    link_bgs = [("bg", surfaces[0]), ("surface", surfaces[1]), ("panel", surfaces[2]), ("hover", surfaces[3]),
                ("brand-soft", soft)] + [(f"{n}-soft", c) for n, c in zip(("accent", "emphasis", "success", "warn", "info"), FIXED_SOFTS[mode])]
    if custom:
        ink = rgb(theme["accent_color"]) if theme.get("accent_color") else fill
        endpoint = INK if mode == "light" else CREAM
        for step in range(101):
            cand = blend(ink, endpoint, step / 100)
            if all(contrast(cand, c) >= 4.5 for _, c in link_bgs):
                ink = cand; break
    else:
        ink = T[mode]["accent-ink"]
    pairs = []
    for name, bg in (("brand", fill), ("brand-hover", hover), ("brand-active", active)):
        pairs.append((f"on-brand on {name}", contrast(fg, bg), 4.5))
    pairs += [(f"brand-ink on {n}", contrast(ink, c), 4.5) for n, c in link_bgs]
    pairs += [(f"{n} on brand-soft", contrast(t, soft), 4.5)
              for n, t in zip(("ink", "muted", "accent-ink", "success-ink", "warn-ink", "info-ink", "danger"), texts)]
    pairs += [(f"brand boundary on {n}", contrast(ink, c), 3) for n, c in link_bgs[:3]]
    return dict(fill=fill, foreground=fg, hover=hover, active=active, soft=soft, ink=ink, pairs=pairs)

def failures(theme):
    return [(m, p, round(r, 2), mn) for m in T for p, r, mn in derive_palette(theme, m)["pairs"] if r < mn]

print("## product default (must equal index.css brand-* tokens)")
for m in T:
    p = derive_palette({}, m)
    worst = min(p["pairs"], key=lambda x: x[1] - x[2])
    print(m, {k: p[k] for k in ("fill", "foreground", "hover", "active", "soft", "ink")}, "worst:", worst[0], round(worst[1], 2))
    for k, tok in (("hover", "accent-hover"), ("active", "accent-active"), ("soft", "accent-soft")):
        print("   ", k, "== index.css", tok, p[k] == T[m][tok], T[m][tok])
print("## golden test inputs")
for theme in ({"primary_color": "#000", "accent_color": "#5a1633"}, {"primary_color": "#fff", "accent_color": "#5a1633"},
              {"primary_color": "#f3c3dd", "accent_color": "#5a1633"}, {"primary_color": "#004400", "accent_color": "#5a1633"},
              {"primary_color": "#abc", "accent_color": "#5a1633"}, {"primary_color": "#004400"}, {"primary_color": "#fff"},
              {"primary_color": "#777"}, {"primary_color": "#f9a8d4"}, {"primary_color": "#e91e63"}, {"primary_color": "#ff7447"}):
    out = []
    for m in T:
        p = derive_palette(theme, m)
        out.append(f"{m}: fill={p['fill']} fg={p['foreground']} hover={p['hover']} active={p['active']} soft={p['soft']} ink={p['ink']}")
    f = failures(theme)
    print(theme, "VALID" if not f else f"INVALID {f[:3]}")
    for o in out: print("   ", o)

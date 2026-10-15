"""Token derivation v2 -- SOURCE-PURE: every value is a brand hex, a linear sRGB-channel mix of brand hexes
(incl. white), or a colour sampled from the Yuyu boards. No OKLCH, no black. Stdlib only.
python -I brand_tokens_v2.py tokens_v2.json
"""
import json, sys

def lum(c):
    f = lambda v: (v/255)/12.92 if v/255 <= 0.04045 else ((v/255 + 0.055)/1.055) ** 2.4
    return sum(f(v)*w for v, w in zip(c, (.2126, .7152, .0722)))
def cr(a, b):
    x, y = sorted((lum(a), lum(b)), reverse=True); return (x + .05)/(y + .05)
def mix(a, b, t):
    return tuple(int(x*(1-t) + y*t + .5) for x, y in zip(a, b))
hx = lambda c: "#%02X%02X%02X" % c

INK, TEAL, ORANGE = (20, 44, 42), (0, 110, 99), (255, 116, 71)
CITRON, SKY, YELLOW, CREAM, WHITE = (223, 255, 143), (181, 205, 255), (255, 212, 71), (255, 244, 232), (255, 255, 255)
Y_RED700, Y_RED800, Y_RED300 = (185, 28, 28), (153, 27, 27), (252, 165, 165)   # sampled: Yuyu org5-settings danger zone
SRC = {}
T = {"light": {}, "dark": {}}
def put(m, k, v, src):
    T[m][k] = v; SRC[(m, k)] = src

# neutrals ------------------------------------------------------------------------------
put("light", "bg", CREAM, "brand")
put("light", "surface", mix(CREAM, INK, .04), "brand-mix: Cream + 4% Ink")
put("light", "panel", WHITE, "brand (white card, p.4/p.16)")
put("light", "hover", mix(CREAM, INK, .07), "brand-mix: Cream + 7% Ink")
put("light", "line", mix(CREAM, INK, .18), "brand-mix: Cream + 18% Ink (p.16 rules = Ink @ 18%)")
put("light", "ink", INK, "brand")
put("dark", "bg", INK, "brand (reversed ground)")
put("dark", "surface", mix(INK, CREAM, .03), "brand-mix: Ink + 3% Cream")
put("dark", "panel", mix(INK, CREAM, .06), "brand-mix: Ink + 6% Cream")
put("dark", "hover", mix(INK, CREAM, .11), "brand-mix: Ink + 11% Cream")
put("dark", "line", mix(INK, CREAM, .15), "brand-mix: Ink + 15% Cream")
put("dark", "ink", CREAM, "brand (reversed text)")
NEUTRAL = {m: [T[m][k] for k in ("bg", "surface", "panel", "hover")] for m in T}
for m, (a, b) in {"light": (CREAM, INK), "dark": (INK, CREAM)}.items():
    for i in range(101):
        c = mix(a, b, i/100)
        if all(cr(c, T[m][k]) >= 3.0 for k in ("bg", "surface", "panel")):
            put(m, "outline", c, f"brand-mix: {'Cream' if m == 'light' else 'Ink'} + {i}% {'Ink' if m == 'light' else 'Cream'}"); break

# fills ------------------------------------------------------------------------------------
for m in T:
    for k, v in (("emphasis", ORANGE), ("success", CITRON), ("warn", YELLOW), ("info", SKY)):
        put(m, k, v, "brand"); put(m, "on-" + k, INK, "brand (tested pair)")
put("light", "accent", TEAL, "brand"); put("light", "on-accent", CREAM, "brand (tested pair 5.68)")
for i in range(101):
    c = mix(TEAL, CREAM, i/100)
    if cr(INK, c) >= 4.6 and all(cr(c, bg) >= 3.0 for bg in NEUTRAL["dark"]):
        put("dark", "accent", c, f"brand-mix: Teal + {i}% Cream"); break
put("dark", "on-accent", INK, "brand")
put("light", "danger", Y_RED700, "Yuyu (sampled #B91C1C)"); put("light", "on-danger", CREAM, "brand")
put("dark", "danger", Y_RED300, "Yuyu (sampled #FCA5A5)"); put("dark", "on-danger", INK, "brand")
put("light", "danger-line", Y_RED300, "Yuyu (sampled #FCA5A5, danger-zone card border)")
put("dark", "danger-line", mix(INK, Y_RED300, .45), "Yuyu-mix: Ink + 45% #FCA5A5")

def shift_target(fill, label):
    away = INK if lum(label) > .5 else CREAM
    toward = CREAM if away == INK else INK
    if cr(mix(fill, away, .10), fill) < 1.06 and cr(label, mix(fill, toward, .20)) >= 4.5:
        return toward
    return away
for m in T:
    for n in ("accent", "emphasis", "success", "warn", "info"):
        tgt = shift_target(T[m][n], T[m]["on-" + n]); nm = "Ink" if tgt == INK else "Cream"
        put(m, n + "-hover", mix(T[m][n], tgt, .10), f"brand-mix: {n} + 10% {nm}")
        put(m, n + "-active", mix(T[m][n], tgt, .20), f"brand-mix: {n} + 20% {nm}")
put("light", "danger-hover", Y_RED800, "Yuyu (sampled #991B1B)")
put("light", "danger-active", mix(Y_RED800, INK, .15), "Yuyu-mix: #991B1B + 15% Ink")
put("dark", "danger-hover", mix(Y_RED300, CREAM, .25), "Yuyu-mix: #FCA5A5 + 25% Cream")
put("dark", "danger-active", mix(Y_RED300, CREAM, .45), "Yuyu-mix: #FCA5A5 + 45% Cream")

SOFT = .12
for m in T:
    for n in ("accent", "emphasis", "success", "warn", "info"):
        put(m, n + "-soft", mix(T[m]["panel"], T[m][n], SOFT), f"brand-mix: panel + 12% {n}")
SOFTS = ("accent", "emphasis", "success", "warn", "info")

# text inks: universal set = neutrals + all softs; solved by mixing the brand colour with Ink (light) / Cream (dark)
def ALL(m): return NEUTRAL[m] + [T[m][n + "-soft"] for n in SOFTS]
def solve(m, seed, name, other, label):
    for i in range(101):
        c = mix(seed, other, i/100)
        if all(cr(c, b) >= 4.6 for b in ALL(m)):
            put(m, name, c, "brand" if i == 0 else f"brand-mix: {label} + {i}% {'Ink' if other == INK else 'Cream'}"); return
    raise SystemExit(name)
for m, other, a, b in (("light", INK, CREAM, INK), ("dark", CREAM, INK, CREAM)):
    best = None
    for i in range(101):
        c = mix(b, a, i/100)
        if all(cr(c, bg) >= 4.6 for bg in ALL(m)): best = (i, c)
    put(m, "muted", best[1], f"brand-mix: {'Ink' if m == 'light' else 'Cream'} + {best[0]}% {'Cream' if m == 'light' else 'Ink'}")
    solve(m, TEAL if m == "light" else T["dark"]["accent"], "accent-ink", other, "Teal" if m == "light" else "dark accent")
    for n, seed, lab in (("success", CITRON, "Citron"), ("warn", YELLOW, "Yellow"), ("info", SKY, "Sky")):
        solve(m, seed, n + "-ink", other, lab)
for m in T:
    put(m, "focus", T[m]["accent-ink"], "= accent-ink")
    for s in ("", "-hover", "-active", "-soft", "-ink"):
        put(m, "brand" + s, T[m]["accent" + s], "= accent" + s + " (tenant-overridable)")
    put(m, "on-brand", T[m]["on-accent"], "= on-accent")
    put(m, "brand-boundary", T[m]["accent-ink"], "= brand-ink")
put("light", "sidebar", CITRON, "brand (p.16 sidebar)"); put("light", "sidebar-hover", mix(CITRON, WHITE, .6), "brand-mix: Citron + 60% white")
put("light", "sidebar-active", TEAL, "brand (p.16 active item)")
put("dark", "sidebar", INK, "brand (Deep Ink)"); put("dark", "sidebar-hover", T["dark"]["hover"], "= hover")
put("dark", "sidebar-active", T["dark"]["accent"], "= accent")

# report -----------------------------------------------------------------------------------
TEXT = ["ink", "muted", "accent-ink", "success-ink", "warn-ink", "info-ink", "danger"]
BGS = ["bg", "surface", "panel", "hover"] + [n + "-soft" for n in SOFTS]
for m in T:
    t = T[m]
    print(f"== {m}")
    for n in TEXT:
        print(f"  {n:12} {hx(t[n])} ({' '.join(map(str, t[n]))})  " + " ".join(f"{b.replace('-soft','~')}:{cr(t[n], t[b]):.2f}" for b in BGS) + f"   [{SRC[(m, n)]}]")
    worst = min((cr(t[a], t[b]), a, b) for a in TEXT for b in BGS); print("  WORST", round(worst[0], 2), worst[1:])
    for n in ("accent", "emphasis", "success", "warn", "info", "danger"):
        lab = t["on-" + n]
        print(f"  on-{n:9} " + ", ".join(f"{k or 'rest'} {hx(t[n + k])} {cr(lab, t[n + k]):.2f}" for k in ("", "-hover", "-active")))
    print(f"  focus vs bg/surface/panel/sidebar: " + ", ".join(f"{cr(t['focus'], t[k]):.2f}" for k in ("bg", "surface", "panel", "sidebar")))
    print(f"  outline vs bg/surface/panel: " + ", ".join(f"{cr(t['outline'], t[k]):.2f}" for k in ("bg", "surface", "panel")))
    print(f"  accent fill vs bg/surface/panel/sidebar: " + ", ".join(f"{cr(t['accent'], t[k]):.2f}" for k in ("bg", "surface", "panel", "sidebar")))
    print(f"  sidebar: ink {cr(t['ink'], t['sidebar']):.2f} muted {cr(t['muted'], t['sidebar']):.2f} accent-ink {cr(t['accent-ink'], t['sidebar']):.2f}; hover ink {cr(t['ink'], t['sidebar-hover']):.2f} muted {cr(t['muted'], t['sidebar-hover']):.2f}; active vs field {cr(t['sidebar-active'], t['sidebar']):.2f}; on-accent on active {cr(t['on-accent'], t['sidebar-active']):.2f}")
    print(f"  danger on panel {cr(t['danger'], t['panel']):.2f}; danger-line vs panel {cr(t['danger-line'], t['panel']):.2f}; ink on line {cr(t['ink'], t['line']):.2f}")
json.dump({"tokens": {m: {k: list(v) for k, v in T[m].items()} for m in T},
           "source": {f"{m}|{k}": v for (m, k), v in SRC.items()}}, open(sys.argv[1], "w"), indent=1)

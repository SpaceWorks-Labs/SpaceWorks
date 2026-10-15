"""Write the extracted logo SVGs (exact PDF geometry, page units = PDF points)."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from logo_list import shapes
from pdf2svg import bbox

OUT = sys.argv[1]
os.makedirs(OUT, exist_ok=True)
HEX = lambda c: '#%02X%02X%02X' % c
BRAND = {'#142C2A': 'Deep Ink', '#006E63': 'Maker Teal', '#FF7447': 'Workshop Orange', '#DFFF8F': 'Citron',
         '#B5CDFF': 'Sky Blue', '#FFD447': 'Warm Yellow', '#FFF4E8': 'Warm Cream'}
cache = {}
def S(page):
    if page not in cache: cache[page] = shapes(page)
    return cache[page]

def transform_shape(sh, s=1.0, dx=0.0, dy=0.0, fill=None):
    d = []
    for seg in sh["d"]:
        if seg[0] == "Z": d.append(seg); continue
        v = list(seg[1:])
        v = [(x * s + dx) if i % 2 == 0 else (x * s + dy) for i, x in enumerate(v)]
        d.append((seg[0],) + tuple(v))
    out = dict(sh); out["d"] = d
    if fill: out["fill"] = fill
    return out

def fmt(v):
    t = '%.3f' % v
    return t.rstrip('0').rstrip('.') if '.' in t else t

def d_of(sh, ox, top):
    parts = []
    for seg in sh["d"]:
        if seg[0] == "Z": parts.append("Z"); continue
        pts = seg[1:]
        parts.append(seg[0] + " ".join(fmt(pts[i] - ox) + " " + fmt(top - pts[i + 1]) for i in range(0, len(pts), 2)))
    return "".join(parts)

def union(bbs):
    return (min(b[0] for b in bbs), min(b[1] for b in bbs), max(b[2] for b in bbs), max(b[3] for b in bbs))

def curve_bbox(sh, steps=24):
    """Tight bbox: sample Beziers instead of using control points."""
    xs, ys, cur = [], [], None
    for seg in sh["d"]:
        k = seg[0]
        if k == "Z": continue
        if k in "ML":
            cur = seg[1:3]; xs.append(cur[0]); ys.append(cur[1])
        elif k == "C":
            x0, y0 = cur; x1, y1, x2, y2, x3, y3 = seg[1:]
            for i in range(steps + 1):
                t = i / steps; u = 1 - t
                xs.append(u**3*x0 + 3*u*u*t*x1 + 3*u*t*t*x2 + t**3*x3)
                ys.append(u**3*y0 + 3*u*u*t*y1 + 3*u*t*t*y2 + t**3*y3)
            cur = (x3, y3)
    return (min(xs), min(ys), max(xs), max(ys))

def write(name, items, title, desc, symbol_idx=None, frame=None, note=""):
    """items: list of shape dicts (already in page coords). symbol_idx: indices within items forming the symbol (for H)."""
    bb = frame or union([curve_bbox(s) for s in items])
    ox, top = bb[0], bb[3]
    w, h = bb[2] - bb[0], bb[3] - bb[1]
    sym = items if symbol_idx is None else [items[i] for i in symbol_idx]
    sb = union([curve_bbox(s) for s in sym])
    H = sb[3] - sb[1]
    colours = sorted({HEX(s["fill"]) for s in items})
    lines = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {fmt(w)} {fmt(h)}" width="{fmt(w)}" height="{fmt(h)}" role="img" aria-labelledby="t">',
             f'  <title id="t">{title}</title>',
             f'  <desc>{desc} Extracted verbatim from docs/brand/space-works-brand-guidelines-v1.pdf; units = PDF points. '
             f'Symbol height H = {fmt(H)}; clear space on every side = H/4 = {fmt(H/4)} (not included in the viewBox). '
             f'Colours: {", ".join(c + " " + BRAND.get(c, "NON-BRAND") for c in colours)}. {note}</desc>']
    for s in items:
        rule = ' fill-rule="evenodd"' if s["rule"] == "evenodd" else ''
        lines.append(f'  <path fill="{HEX(s["fill"])}"{rule} d="{d_of(s, ox, top)}"/>')
    lines.append('</svg>\n')
    open(os.path.join(OUT, name), 'w', encoding='utf-8', newline='\n').write("\n".join(lines))
    return dict(name=name, w=w, h=h, H=H, colours=colours, symbol_w=sb[2]-sb[0])

def pick(page, idx):
    return [S(page)[i] for i in idx]

R = []
R.append(write('symbol.svg', pick(3, range(9, 16)), 'Space Works symbol',
               'Full-colour symbol master (p.3, largest instance).'))
R.append(write('lockup-stacked.svg', pick(4, range(10, 18)), 'space works',
               'Primary lockup: symbol + two-line wordmark, full colour for cream/white (p.4).', symbol_idx=range(0, 7)))
R.append(write('lockup-horizontal.svg', pick(4, range(29, 37)), 'space works',
               'Horizontal lockup for narrow headers, full colour (p.4, shown on Citron).', symbol_idx=range(0, 7)))
R.append(write('lockup-stacked-reversed.svg', pick(4, range(39, 46)), 'space works',
               'Reversed primary lockup, Warm Cream one-colour artwork for Deep Ink or Maker Teal grounds (p.4; identical artwork on p.7 03/04 and the cover).', symbol_idx=range(0, 6)))
R.append(write('symbol-reversed.svg', pick(4, range(39, 45)), 'Space Works symbol',
               'Reversed symbol, Warm Cream one-colour artwork (p.4).'))
R.append(write('lockup-stacked-one-colour-ink.svg', pick(7, range(21, 28)), 'space works',
               'One-colour Deep Ink lockup (p.7 variant 02, on white).', symbol_idx=range(0, 6)))
R.append(write('symbol-one-colour-ink.svg', pick(7, range(21, 27)), 'Space Works symbol',
               'One-colour Deep Ink symbol (p.7 variant 02).'))

# App icon: p.6 tile (shape 32) + symbol 34-40, framed by the tile itself.
tile = S(6)[32]
R.append(write('app-icon.svg', [tile] + pick(6, range(34, 41)), 'Space Works app icon',
               'App icon master (p.6): Warm Cream tile with the full-colour symbol; placement exactly as drawn in the PDF.',
               symbol_idx=range(1, 8), frame=curve_bbox(tile)))

# Horizontal reversed: NOT in the PDF. Assembled from the reversed symbol master (p.4, cream) mapped onto the
# horizontal lockup's symbol box via the top-left flap, plus the horizontal wordmark in Warm Cream.
full = S(4); rev = S(4)
f_flap, r_flap = curve_bbox(full[32]), curve_bbox(rev[41])          # top-left flaps
s = ((f_flap[2]-f_flap[0])/(r_flap[2]-r_flap[0]) + (f_flap[3]-f_flap[1])/(r_flap[3]-r_flap[1])) / 2
dx, dy = f_flap[0] - r_flap[0]*s, f_flap[1] - r_flap[1]*s
sym = [transform_shape(rev[i], s, dx, dy) for i in range(39, 45)]
word = transform_shape(full[36], fill=(255, 244, 232))
R.append(write('lockup-horizontal-reversed.svg', sym + [word], 'space works',
               'ASSEMBLED, NOT A PDF MASTER: the PDF contains no reversed horizontal lockup.',
               symbol_idx=range(0, 6),
               note=f'Built from the p.4 reversed symbol (scaled x{s:.5f} onto the horizontal lockup symbol box by matching the top-left flap) and the p.4 horizontal wordmark recoloured Warm Cream. Owner must approve or supply a master.'))

for r in R:
    print(f"{r['name']:36} {r['w']:8.2f} x {r['h']:7.2f}  H={r['H']:7.2f}  symbolW/H={r['symbol_w']/r['H']:.4f}  w/H={r['w']/r['H']:.4f}  {r['colours']}")

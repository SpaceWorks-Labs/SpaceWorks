"""Exact vector extraction from the brand PDF (stdlib only).

Parses a page content stream (already inflated into pdfx/pageN.txt by pdfx2.py) and returns every
painted path in PAGE coordinates (PDF user space, y up), with its fill colour, fill rule, alpha and
whether it was painted under a clip. Transforms (cm) are applied to the points, so the output path
data is exact -- no simplification, no re-fitting.
"""
import re

TOKEN = re.compile(rb'\[[^\]]*\]|\((?:\\.|[^\\)])*\)|<<|>>|<[0-9A-Fa-f\s]*>|/[^\s/\[\]()<>{}]+|[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?|[A-Za-z*\'"]+|\S')
NUM = re.compile(rb'^[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?$')


def mul(a, b):
    return [a[0]*b[0] + a[1]*b[2], a[0]*b[1] + a[1]*b[3],
            a[2]*b[0] + a[3]*b[2], a[2]*b[1] + a[3]*b[3],
            a[4]*b[0] + a[5]*b[2] + b[4], a[4]*b[1] + a[5]*b[3] + b[5]]


def parse(content, ext_alpha=None):
    ext_alpha = ext_alpha or {}
    ctm = [1, 0, 0, 1, 0, 0]
    state = {"fill": (0, 0, 0), "stroke": (0, 0, 0), "ca": 1.0, "clipped": False, "lw": 1.0}
    stack = []
    ops = []          # numeric operand stack
    path = []         # list of segments: ("M",x,y) ("L",x,y) ("C",x1,y1,x2,y2,x,y) ("Z",)
    cur = None
    start = None
    pending_clip = False
    shapes = []
    in_text = False

    def T(x, y):
        return (ctm[0]*x + ctm[2]*y + ctm[4], ctm[1]*x + ctm[3]*y + ctm[5])

    def paint(fill, stroke, rule):
        nonlocal path, pending_clip
        if path and not in_text:
            shapes.append({"d": path, "fill": state["fill"] if fill else None,
                           "stroke": state["stroke"] if stroke else None, "rule": rule,
                           "ca": state["ca"], "clipped": state["clipped"],
                           "lw": state["lw"] * (abs(ctm[0]*ctm[3] - ctm[1]*ctm[2]) ** .5)})
        if pending_clip:
            state["clipped"] = True
            pending_clip = False
        path = []

    for tok in TOKEN.findall(content):
        if NUM.match(tok):
            ops.append(float(tok)); continue
        t = tok.decode('latin1')
        if t == 'BT': in_text = True
        elif t == 'ET': in_text = False
        elif t == 'q': stack.append((ctm[:], dict(state)))
        elif t == 'Q': ctm, state = stack.pop()
        elif t == 'cm' and len(ops) >= 6: ctm = mul(ops[-6:], ctm)
        elif t in ('scn', 'sc', 'rg') and len(ops) >= 3 and not in_text: state["fill"] = tuple(round(v * 255) for v in ops[-3:])
        elif t in ('SCN', 'SC', 'RG') and len(ops) >= 3: state["stroke"] = tuple(round(v * 255) for v in ops[-3:])
        elif t == 'g' and ops: state["fill"] = (round(ops[-1]*255),)*3
        elif t == 'k' and len(ops) >= 4:
            c, m, y, k = ops[-4:]
            state["fill"] = tuple(round(255*(1-v)*(1-k)) for v in (c, m, y))
        elif t == 'w' and ops: state["lw"] = ops[-1]
        elif t == 'gs': pass
        elif t.startswith('/') and t[1:] in ext_alpha: state["ca"] = ext_alpha[t[1:]]
        elif t == 'm' and len(ops) >= 2:
            cur = T(*ops[-2:]); start = cur; path.append(("M",) + cur)
        elif t == 'l' and len(ops) >= 2:
            cur = T(*ops[-2:]); path.append(("L",) + cur)
        elif t == 'c' and len(ops) >= 6:
            p1, p2, p3 = T(*ops[-6:-4]), T(*ops[-4:-2]), T(*ops[-2:])
            path.append(("C",) + p1 + p2 + p3); cur = p3
        elif t == 'v' and len(ops) >= 4:
            p2, p3 = T(*ops[-4:-2]), T(*ops[-2:])
            path.append(("C",) + cur + p2 + p3); cur = p3
        elif t == 'y' and len(ops) >= 4:
            p1, p3 = T(*ops[-4:-2]), T(*ops[-2:])
            path.append(("C",) + p1 + p3 + p3); cur = p3
        elif t == 'h':
            path.append(("Z",)); cur = start
        elif t == 're' and len(ops) >= 4:
            x, y, w, h = ops[-4:]
            pts = [T(x, y), T(x + w, y), T(x + w, y + h), T(x, y + h)]
            path += [("M",) + pts[0], ("L",) + pts[1], ("L",) + pts[2], ("L",) + pts[3], ("Z",)]
            cur = start = pts[0]
        elif t in ('W', 'W*'): pending_clip = True
        elif t in ('f', 'F'): paint(True, False, 'nonzero')
        elif t == 'f*': paint(True, False, 'evenodd')
        elif t in ('B', 'b'): paint(True, True, 'nonzero')
        elif t in ('B*', 'b*'): paint(True, True, 'evenodd')
        elif t in ('S', 's'): paint(False, True, 'nonzero')
        elif t == 'n':
            path = []
            if pending_clip:
                state["clipped"] = True; pending_clip = False
        if not t.startswith('/'):
            ops = []
    return shapes


def bbox(shape):
    xs, ys = [], []
    for seg in shape["d"]:
        v = seg[1:]
        xs += v[0::2]; ys += v[1::2]
    return (min(xs), min(ys), max(xs), max(ys)) if xs else None


def svg_d(shape, ox, top, nd=3):
    """PDF page coords -> SVG coords: x' = x - ox, y' = top - y."""
    f = lambda v: ('%.*f' % (nd, v)).rstrip('0').rstrip('.') if '.' in '%.*f' % (nd, v) else '%.*f' % (nd, v)
    out = []
    for seg in shape["d"]:
        k = seg[0]
        if k == "Z": out.append("Z"); continue
        pts = seg[1:]
        coords = []
        for i in range(0, len(pts), 2):
            coords += [f(pts[i] - ox), f(top - pts[i + 1])]
        out.append(k + " ".join(coords))
    return "".join(out)

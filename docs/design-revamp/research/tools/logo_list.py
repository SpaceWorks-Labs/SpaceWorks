import pickle, re, sys
sys.path.insert(0, '.')
from pdf2svg import parse, bbox
objs = pickle.load(open('pdfx/objs.pkl', 'rb'))
PAGES = [191, 517, 825, 1139, 1463, 1919, 2217, 2585, 3165, 3584, 3930, 4432, 4770, 5246, 5694, 6190, 6614]
def alphas(pn):
    b = objs[PAGES[pn-1]]
    r = re.search(rb'/Resources\s+(\d+) 0 R', b)
    res = objs[int(r.group(1))] if r else b
    return {m.group(1).decode(): float(m.group(2)) for m in re.finditer(rb'/(E\d+)\s*<<[^>]*?/ca\s+([\d.]+)', res)}
def shapes(pn):
    return parse(open(f'pdfx/page{pn}.txt', 'rb').read(), alphas(pn))
if __name__ == '__main__':
    pn = int(sys.argv[1])
    print('alphas', alphas(pn))
    for i, s in enumerate(shapes(pn)):
        b = bbox(s)
        if not b or (b[2]-b[0] < 3 and b[3]-b[1] < 3): continue
        col = '#%02X%02X%02X' % s['fill'] if s['fill'] else '-'
        st = '#%02X%02X%02X' % s['stroke'] if s['stroke'] else '-'
        print(i, col, 'stroke', st, 'ca', s['ca'], 'clip' if s['clipped'] else '', s['rule'], 'segs', len(s['d']), 'bbox', tuple(round(v,1) for v in b))

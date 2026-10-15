import re, zlib, sys, json
data = open(sys.argv[1],'rb').read()
objs = {}
for m in re.finditer(rb'(\d+)\s+0\s+obj(.*?)endobj', data, re.S):
    objs[int(m.group(1))] = m.group(2)
def stream(body):
    m = re.search(rb'stream\r?\n(.*?)endstream', body, re.S)
    if not m: return None
    raw = m.group(1).rstrip(b'\r\n')
    if b'FlateDecode' in body[:m.start()]:
        try: return zlib.decompress(raw)
        except Exception:
            try: return zlib.decompressobj().decompress(raw)
            except Exception: return None
    return raw
# expand object streams
for n,b in list(objs.items()):
    if b'/ObjStm' in b[:300]:
        s = stream(b)
        if s is None: continue
        N = int(re.search(rb'/N\s+(\d+)', b).group(1)); F = int(re.search(rb'/First\s+(\d+)', b).group(1))
        hdr = s[:F].split()
        for i in range(N):
            on, off = int(hdr[2*i]), int(hdr[2*i+1])
            end = int(hdr[2*i+3]) if i+1<N else len(s)-F
            objs.setdefault(on, s[F+off:F+end])
pages = sorted(n for n,b in objs.items() if re.search(rb'/Type\s*/Page(?!s)', b))
print("pages", pages)
import pickle
out = {}
for idx,n in enumerate(pages,1):
    b = objs[n]
    c = re.search(rb'/Contents\s*(\[[^\]]*\]|\d+ 0 R)', b)
    refs = [int(x) for x in re.findall(rb'(\d+) 0 R', c.group(1))] if c else []
    mb = re.search(rb'/MediaBox\s*\[([^\]]*)\]', b)
    content = b''.join((stream(objs[r]) or b'') for r in refs)
    xo = re.findall(rb'/(\w+)\s+(\d+) 0 R', (re.search(rb'/XObject\s*<<(.*?)>>', b, re.S) or re.search(rb'()',b)).group(1) or b'')
    print(idx, n, mb.group(1) if mb else None, len(content), 'xobj', xo[:6])
    open(f'pdfx/page{idx}.txt','wb').write(content)
pickle.dump(objs, open('pdfx/objs.pkl','wb'))

import zlib, struct
def load(path):
    d = open(path, 'rb').read(); assert d[:8] == b'\x89PNG\r\n\x1a\n'
    i = 8; idat = b''; w = h = None
    while i < len(d):
        ln, typ = struct.unpack('>I4s', d[i:i+8]); body = d[i+8:i+8+ln]; i += 12 + ln
        if typ == b'IHDR': w, h, bd, ct, _, _, il = struct.unpack('>IIBBBBB', body)
        elif typ == b'IDAT': idat += body
        elif typ == b'IEND': break
    assert bd == 8 and il == 0, (bd, il)
    bpp = {2: 3, 6: 4, 0: 1, 4: 2}[ct]
    raw = zlib.decompress(idat); stride = w * bpp; rows = []; prev = bytearray(stride); p = 0
    for y in range(h):
        f = raw[p]; line = bytearray(raw[p+1:p+1+stride]); p += 1 + stride
        for x in range(stride):
            a = line[x-bpp] if x >= bpp else 0; b = prev[x]; c = prev[x-bpp] if x >= bpp else 0
            if f == 1: line[x] = (line[x] + a) & 255
            elif f == 2: line[x] = (line[x] + b) & 255
            elif f == 3: line[x] = (line[x] + (a + b) // 2) & 255
            elif f == 4:
                pp = a + b - c; pa, pb, pc = abs(pp-a), abs(pp-b), abs(pp-c)
                line[x] = (line[x] + (a if pa <= pb and pa <= pc else b if pb <= pc else c)) & 255
        rows.append(bytes(line)); prev = line
    def px(x, y):
        r = rows[y]; o = x * bpp
        return tuple(r[o:o+3]) if bpp >= 3 else (r[o],)*3
    return w, h, px

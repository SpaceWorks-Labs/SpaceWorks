import struct, sys
def tables(data):
    num = struct.unpack('>H', data[4:6])[0]
    t = {}
    for i in range(num):
        tag, cs, off, ln = struct.unpack('>4sIII', data[12+16*i:28+16*i])
        t[tag.decode('latin1')] = (off, ln)
    return t
def name_table(data, off):
    fmt, count, so = struct.unpack('>HHH', data[off:off+6]); out = {}
    for i in range(count):
        pid, eid, lid, nid, ln, o = struct.unpack('>HHHHHH', data[off+6+12*i:off+18+12*i])
        raw = data[off+so+o: off+so+o+ln]
        if pid == 3: s = raw.decode('utf-16-be', 'replace')
        elif pid == 1: s = raw.decode('latin1')
        else: continue
        out.setdefault(nid, s)
    return out
def cmap_has(data, off, cp):
    ver, n = struct.unpack('>HH', data[off:off+4])
    for i in range(n):
        pid, eid, so = struct.unpack('>HHI', data[off+4+8*i:off+12+8*i])
        sub = off + so; fmt = struct.unpack('>H', data[sub:sub+2])[0]
        if fmt == 4:
            segx2 = struct.unpack('>H', data[sub+6:sub+8])[0]; seg = segx2//2
            ends = struct.unpack('>%dH' % seg, data[sub+14:sub+14+segx2])
            starts = struct.unpack('>%dH' % seg, data[sub+16+segx2:sub+16+2*segx2])
            if any(s <= cp <= e for s, e in zip(starts, ends)): return True
        if fmt == 12:
            ng = struct.unpack('>I', data[sub+12:sub+16])[0]
            for g in range(ng):
                s, e, _ = struct.unpack('>III', data[sub+16+12*g:sub+28+12*g])
                if s <= cp <= e: return True
    return False
for path in sys.argv[1:]:
    d = open(path, 'rb').read(); t = tables(d)
    head = t['head'][0]; upm = struct.unpack('>H', d[head+18:head+20])[0]
    os2 = t['OS/2'][0]; ver = struct.unpack('>H', d[os2:os2+2])[0]
    avg = struct.unpack('>h', d[os2+2:os2+4])[0]; wght = struct.unpack('>H', d[os2+4:os2+6])[0]; wdth = struct.unpack('>H', d[os2+6:os2+8])[0]
    fstype = struct.unpack('>H', d[os2+8:os2+10])[0]
    asc, desc, gap = struct.unpack('>hhh', d[os2+68:os2+74]); wasc, wdesc = struct.unpack('>HH', d[os2+74:os2+78])
    xh = ch = None
    if ver >= 2: xh, ch = struct.unpack('>hh', d[os2+86:os2+90])
    hhea = t['hhea'][0]; ha, hd, hg = struct.unpack('>hhh', d[hhea+4:hhea+10])
    maxp = t['maxp'][0]; ng = struct.unpack('>H', d[maxp+4:maxp+6])[0]
    n = name_table(d, t['name'][0])
    print(path.split('/')[-1], 'tables', sorted(t))
    print('  family', n.get(1), '| sub', n.get(2), '| full', n.get(4), '| version', n.get(5), '| ps', n.get(6), '| typo-fam', n.get(16), n.get(17))
    print('  upm', upm, 'weightClass', wght, 'widthClass', wdth, 'fsType', fstype, 'xAvgCharWidth', avg, 'glyphs', ng)
    print('  typo asc/desc/gap', asc, desc, gap, 'win', wasc, wdesc, 'hhea', ha, hd, hg, 'xHeight', xh, 'capHeight', ch, 'x/cap', round(xh/ch,3) if xh and ch else None, 'x/upm', round(xh/upm,3) if xh else None)
    print('  has U+20B9 rupee', cmap_has(d, t['cmap'][0], 0x20B9), 'U+20AC euro', cmap_has(d, t['cmap'][0], 0x20AC), 'U+0410 cyrillic', cmap_has(d, t['cmap'][0], 0x410))
    print('  copyright', (n.get(0) or '')[:160]); print('  license', (n.get(13) or '')[:200], n.get(14))

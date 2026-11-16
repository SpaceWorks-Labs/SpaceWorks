"""Structural binary checks, with explicit weak/proprietary confidence."""
import re
import struct
import zlib

from .errors import FormatError

OLE2 = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"


def _gzip(reader, *, expected=None):
    prefix = reader.read(0, min(10, reader.size))
    if len(prefix) != 10 or prefix[:3] != b"\x1f\x8b\x08" or prefix[3] & 0xe0:
        raise FormatError("invalid_gzip")
    if expected is None:
        return  # No tar/ODB extraction or claims about inner semantics.
    decoder, total, first = zlib.decompressobj(31), 0, b""
    try:
        for chunk in reader.chunks(65536):
            while chunk:
                data = decoder.decompress(chunk, 65536)
                total += len(data)
                first = (first + data)[:128]
                chunk = decoder.unconsumed_tail
                if total > 1024 ** 3 or total > reader.size * 100:
                    raise FormatError("archive_ratio", 413)
        if not decoder.eof or decoder.unused_data or not first.lstrip(b"\xef\xbb\xbf \t\r\n").startswith(expected):
            raise FormatError("invalid_gzip")
    except zlib.error as exc:
        raise FormatError("invalid_gzip") from exc


def check_binary(reader, spec):
    p = reader.read(0, min(65536, reader.size))
    ext, sub, size = spec.extension, spec.subtype, reader.size
    valid = False
    if sub == "zip":
        from .signatures_zip import check_zip
        return check_zip(reader, spec)
    if ext == "stl":
        binary = size >= 84 and size == 84 + 50 * struct.unpack_from("<I", p, 80)[0]
        if sub == "binary":
            valid = binary and size > 84
        elif not binary:
            from .signatures_text import text_prefix
            text = text_prefix(reader, spec)
            tail = reader.read(max(0, size - 512), min(size, 512))
            valid = text.lstrip().startswith("solid") and "facet normal" in text and b"endsolid" in tail
    elif ext == "dxf":
        valid = (p.startswith(b"AutoCAD Binary DXF\r\n\x1a\x00") if sub == "binary"
                 else bool(re.match(br"\s*0\s*\r?\nSECTION\s*\r?\n", p)))
    elif sub == "pdf":
        valid = p.startswith(b"%PDF-") and b"%%EOF" in reader.read(max(0, size - 1024), min(1024, size))
        if valid:
            from .pdf_validation import check_pdf
            check_pdf(reader)
    elif ext == "ai":
        valid = p.startswith(b"%!PS-Adobe") if sub == "postscript" else False
    elif ext == "eps":
        valid = (p.startswith(b"\xc5\xd0\xd3\xc6") and size >= 30 if sub == "dos"
                 else p.startswith(b"%!PS-Adobe") and b"EPSF" in p.split(b"\n", 1)[0])
    elif ext == "cdr":
        valid = len(p) >= 12 and p[:4] == b"RIFF" and p[8:11].lower() == b"cdr"
    elif ext == "ply":
        encoding = {"ascii": b"ascii", "little": b"binary_little_endian", "big": b"binary_big_endian"}[sub]
        valid = p.startswith(b"ply\nformat " + encoding + b" 1.0\n") and b"end_header\n" in p
    elif ext == "bgcode":
        valid = len(p) >= 10 and p[:4] == b"GCDE" and struct.unpack_from("<I", p, 4)[0] == 1
    elif ext == "stpz":
        _gzip(reader, expected=b"ISO-10303-21;")
        valid = True
    elif sub in {"gzip", "odb"}:
        _gzip(reader)
        valid = size >= 18
    elif sub == "ole2":
        valid = size >= 512 and p.startswith(OLE2) and p[28:30] == b"\xfe\xff"
    elif ext == "skp":
        valid = p.startswith(b"\xff\xfe\xff\x0e") and "SketchUp Model".encode("utf-16le") in p[:128]
    elif ext == "blend":
        if sub == "gzip":
            _gzip(reader, expected=b"BLENDER")
            valid = True
        elif sub == "zstd":
            valid = size >= 12 and p.startswith(b"\x28\xb5\x2f\xfd")
        else:
            valid = bool(re.match(br"BLENDER[_-][vV]\d{3}", p))
    elif ext == "dwg":
        valid = size >= 32 and p[:6] in {b"AC1015", b"AC1018", b"AC1021", b"AC1024", b"AC1027", b"AC1032"}
    elif ext == "3dm":
        valid = p.startswith(b"3D Geometry File Format ") and size >= 32
    elif ext == "uf2":
        valid = size % 512 == 0
        count = size // 512
        for number in range(count) if valid else ():
            block = reader.read(number * 512, 512)
            a, b, _, _, payload, index, total = struct.unpack_from("<7I", block)
            if (a != 0x0a324655 or b != 0x9e5d5157 or not 1 <= payload <= 476 or
                    index != number or total != count or block[508:] != b"\x30\x6f\xb1\x0a"):
                valid = False
                break
    elif ext == "elf":
        machine = {"arm": 40, "avr": 83, "xtensa": 94, "riscv": 243}[sub]
        valid = (len(p) >= 52 and p[:4] == b"\x7fELF" and p[4] in (1, 2) and
                 p[5] in (1, 2) and int.from_bytes(p[18:20], "little" if p[5] == 1 else "big") == machine)
    elif ext == "pes":
        valid = bool(re.match(br"#PES\d{4}", p)) and size >= 12
    elif ext == "dst":
        valid = p.startswith(b"LA:") and size >= 515 and (size - 512) % 3 == 0
    elif ext == "jef":
        valid = size >= 124 and 116 <= struct.unpack_from("<I", p)[0] < size
    elif ext == "exp":
        valid = size >= 2 and size % 2 == 0
    elif ext == "vp3":
        valid = p.startswith(b"%vsm%") and size >= 12
    elif ext == "7z":
        valid = size >= 32 and p.startswith(b"7z\xbc\xaf\x27\x1c") and p[6] == 0
    elif sub == "isobmff":
        valid = size >= 16 and p[4:8] == b"ftyp" and 16 <= int.from_bytes(p[:4], "big") <= size
    elif sub == "ebml":
        valid = size >= 12 and p.startswith(b"\x1a\x45\xdf\xa3")
    elif sub == "opaque":
        valid = True  # No invented proprietary signature; universal rejects run first.
    if not valid:
        raise FormatError("binary_subtype_mismatch")

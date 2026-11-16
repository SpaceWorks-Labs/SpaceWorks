import pytest
from apps.maker_formats.errors import FormatError
from apps.maker_formats.range_reader import BytesReader
from apps.maker_formats.registry import REGISTRY
from apps.maker_formats.validation import validate
from .samples import SAMPLES, binary_stl, uf2, elf, archive


@pytest.mark.parametrize("ext,sub,data", [
    ("stl", "binary", binary_stl()[:-1]), ("stl", "ascii", b"solid cube"),
    ("hex", "intelhex", b":0100000001FF\n:00000001FF"),
    ("hex", "intelhex", b":0100000001FE"), ("hex", "intelhex", b":00000001FF\n:00000001FF"),
    ("uf2", "uf2", uf2()[:-1]), ("uf2", "uf2", uf2()[:-4] + b"xxxx"),
    ("elf", "arm", elf(3)), ("elf", "arm", elf(62)),
    ("gcode", "gcode", b";" + b"a" * (1024**2) + b"\nG1 X0\n"),
    ("gcode", "gcode", b"(G1 X0)\n;G1 X0\n"), ("gbr", "gerber", b"plain text*"),
    ("asc", "utf16le", b"\xfe\xff" + "Version 4\nSHEET 1".encode("utf-16be")),
    ("3mf", "core", archive({"README.txt": b"no model"})),
    ("zip", "gerber", archive({"README.txt": b"no board"})),
    ("fcstd", "freecad", archive({"README.txt": b"no document"})),
    ("fzz", "fritzing", archive({"README.txt": b"no module"})),
    ("json", "easyeda", b"{\"not_editor\":1}"), ("kicad_pro", "kicad_project", b"{}"),
    ("obj", "obj", b"v 1 2 3\n\x00"), ("obj", "obj", b"v 1 2 3\n\xff"),
    ("tar.gz", "gzip", b"\x1f\x8b\x08"), ("7z", "7z", b"7z\xbc\xaf\x27\x1c"),
    ("png", "png", b"%PDF-1.5\n%%EOF"), ("pdf", "pdf", b"\x89PNG\r\n\x1a\n"),
])
def test_malformed_content(ext, sub, data):
    with pytest.raises(FormatError):
        validate(BytesReader(data), REGISTRY[ext, sub])


@pytest.mark.parametrize("ext,sub", [("svg", "svg"), ("amf", "xml"), ("lbrn2", "lightburn"),
                                      ("xml", "ipc2581"), ("brd", "eagle")])
@pytest.mark.parametrize("declaration", [b'<!ENTITY a "AAAA">', b'<!DOCTYPE a SYSTEM "https://bad.example/x">',
                                          b'<!DOCTYPE a [<!ENTITY a "&a;&a;">]>'])
def test_entities_and_foreign_dtd_even_after_large_prefix(ext, sub, declaration):
    data = b" " * 70000 + declaration + SAMPLES[ext, sub]()
    with pytest.raises(FormatError):
        validate(BytesReader(data), REGISTRY[ext, sub])


@pytest.mark.parametrize("body", [b'<svg onload="alert(1)"/>', b"<svg><foreignObject/></svg>",
    b'<svg><a href="javascript:alert(1)"/></svg>', b'<svg><image href="https://example.com/x"/></svg>',
    b'<svg><path style="fill:url(https://example.com/x)"/></svg>', b"<svg><script/></svg>"])
def test_svg_active_content(body):
    with pytest.raises(FormatError):
        validate(BytesReader(body), REGISTRY["svg", "svg"])


def test_binary_stl_solid_header_wins_and_all_uf2_blocks_checked():
    validate(BytesReader(binary_stl(True)), REGISTRY["stl", "binary"])
    data = bytearray(uf2(3))
    data[512 + 508] ^= 0xff
    with pytest.raises(FormatError):
        validate(BytesReader(bytes(data)), REGISTRY["uf2", "uf2"])

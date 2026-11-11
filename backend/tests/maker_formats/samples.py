"""Generated STRUCTURAL policy fixtures, not verified proprietary real exports.

Independent extension/subtype inventory deliberately repeats the public matrix:
the drift test fails when a registry variant has no explicit fixture builder.
"""
from functools import partial
from io import BytesIO
import gzip
import json
import struct
import zipfile

from PIL import Image


def archive(entries):
    out = BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_STORED) as handle:
        for name, data in entries.items():
            handle.writestr(name, data)
    return out.getvalue()


def three_mf(subtype):
    entries = {"[Content_Types].xml": b"<Types/>", "_rels/.rels": b"<Relationships/>",
               "3D/3dmodel.model": b'<model xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02"/>'}
    if subtype == "prusa":
        entries["Metadata/Slic3r_PE.config"] = b"layer_height=0.2"
    elif subtype in {"bambu", "orca"}:
        entries["Metadata/project_settings.config"] = b"{}"
        if subtype == "orca":
            entries["Metadata/orca.config"] = b"{}"
    elif subtype == "sliced":
        entries["Metadata/plate_1.gcode"] = b"G1 X0 Y0"
    return archive(entries)


def binary_stl(solid=False):
    return (b"solid" if solid else b"structural").ljust(80, b" ") + struct.pack("<I12fH", 1, *([0.] * 12), 0)


def uf2(count=2):
    return b"".join(struct.pack("<8I", 0x0a324655, 0x9e5d5157, 0, 0x1000 + i * 256,
        256, i, count, 0).ljust(508, b"\0") + struct.pack("<I", 0x0ab16f30) for i in range(count))


def elf(machine):
    data = bytearray(64)
    data[:7] = b"\x7fELF\x01\x01\x01"
    struct.pack_into("<H", data, 18, machine)
    return bytes(data)


def image(kind):
    output = BytesIO()
    Image.new("RGB", (4, 4), (20, 44, 42)).save(output, format=kind)
    return output.getvalue()


def pdf():
    objects = [b"<</Type/Catalog/Pages 2 0 R>>", b"<</Type/Pages/Kids[3 0 R]/Count 1>>",
               b"<</Type/Page/Parent 2 0 R/MediaBox[0 0 100 100]>>"]
    data, offsets = b"%PDF-1.4\n", [0]
    for number, obj in enumerate(objects, 1):
        offsets.append(len(data))
        data += f"{number} 0 obj\n".encode() + obj + b"\nendobj\n"
    xref = len(data)
    data += b"xref\n0 4\n0000000000 65535 f \n"
    for offset in offsets[1:]:
        data += f"{offset:010d} 00000 n \n".encode()
    return data + b"trailer\n<</Size 4/Root 1 0 R>>\nstartxref\n" + str(xref).encode() + b"\n%%EOF\n"


def sample(extension, subtype):
    if extension in {"3mf", "gcode.3mf"}:
        return three_mf(subtype)
    if extension in {"jpg", "jpeg", "png", "webp"}:
        return image({"jpg": "JPEG", "jpeg": "JPEG", "png": "PNG", "webp": "WEBP"}[extension])
    if subtype == "eagle":
        return b'<?xml version="1.0"?><!DOCTYPE eagle SYSTEM "eagle.dtd"><eagle version="9.6.2"><drawing/></eagle>'
    if subtype == "ole2":
        data = bytearray(512)
        data[:8] = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
        data[28:30] = b"\xfe\xff"
        return bytes(data)
    if subtype == "gcode":
        return (b";" + b"thumbnail-comment" * 6000 + b"\nN42 G1 X0 Y0\n")
    if subtype == "gerber" and extension != "zip":
        return b"G04 structural fixture*\n%FSLAX26Y26*%\n%MOMM*%\nX0Y0D02*\nM02*\n"
    if subtype == "excellon":
        return b";drill\nM48\nMETRIC\nT1C0.8\n%\nT1\nX0Y0\nM30\n"
    if subtype == "source" and extension != "zip":
        return b"#!/usr/bin/env python3\nprint('inert fixture')\n" if extension == "py" else b"// structural source\nint fixture = 1;\n"
    if subtype in {"kicad_pcb", "kicad_sch", "kicad_symbol_lib", "footprint", "module"}:
        return f"({subtype} (version 20240108))".encode()
    if subtype == "kicad5":
        return {"sch": b"EESchema Schematic File Version 4\n$EndSCHEMATC\n",
                "pro": b"[general]\nversion=1\n", "lib": b"EESchema-LIBRARY Version 2.4\n#End Library\n"}[extension]
    if subtype == "opaque":
        data = b"Structural opaque fixture\x01\x02\x03\x04\x05"
        return data + b"\0" * (len(data) % 2) if extension == "exp" else data
    if extension == "stl":
        return binary_stl(True) if subtype == "binary" else b"solid test\nfacet normal 0 0 1\nouter loop\nvertex 0 0 0\nvertex 1 0 0\nvertex 0 1 0\nendloop\nendfacet\nendsolid test\n"
    if extension == "dxf":
        return b"AutoCAD Binary DXF\r\n\x1a\x00\0" if subtype == "binary" else b"0\nSECTION\n2\nENTITIES\n0\nENDSEC\n0\nEOF\n"
    if subtype == "pdf":
        return pdf()
    if extension == "ai":
        return b"%!PS-Adobe-3.0\n%%BoundingBox: 0 0 10 10\nshowpage\n"
    if extension == "eps":
        return b"\xc5\xd0\xd3\xc6" + b"\0" * 30 if subtype == "dos" else b"%!PS-Adobe-3.0 EPSF-3.0\n%%BoundingBox: 0 0 1 1\n"
    if extension == "cdr":
        return b"RIFF\x04\0\0\0CDR0" if subtype == "riff" else archive({"content/root.dat": b"fixture"})
    if extension in {"lbrn", "lbrn2"}:
        return b'<LightBurnProject AppVersion="1.7"><Shape Type="Rect"/></LightBurnProject>'
    if extension == "svg":
        return b'<svg xmlns="http://www.w3.org/2000/svg"><path d="M0 0L1 1"/></svg>'
    if extension == "amf":
        return b"<amf unit=\"millimeter\"><object id=\"0\"/></amf>" if subtype == "xml" else archive({"part.amf": b"<amf/>"})
    if extension == "ply":
        encoding = {"ascii": "ascii", "little": "binary_little_endian", "big": "binary_big_endian"}[subtype]
        return f"ply\nformat {encoding} 1.0\nelement vertex 0\nend_header\n".encode()
    if extension in {"step", "stp"}:
        return b"ISO-10303-21;\nHEADER;\nENDSEC;\nDATA;\nENDSEC;\nEND-ISO-10303-21;"
    if extension == "stpz":
        return gzip.compress(sample("step", "step"))
    if extension in {"iges", "igs"}:
        return b"structural IGES".ljust(72, b" ") + b"S      1\n"
    if extension == "blend":
        return {"plain": b"BLENDER-v405" + b"\0" * 20,
                "gzip": gzip.compress(b"BLENDER-v405" + b"\0" * 20),
                "zstd": b"\x28\xb5\x2f\xfd\x20\x0c\x61\x00\x00BLENDER-v405"}[subtype]
    if extension == "skp":
        return b"\xff\xfe\xff\x0e" + "SketchUp Model".encode("utf-16le")
    if extension == "dwg":
        return b"AC1032".ljust(64, b"\0")
    if extension == "3dm":
        return b"3D Geometry File Format 80".ljust(64, b"\0")
    if extension == "f3d":
        return archive({"FusionDocument.json": b"{}"})
    containers = {"fcstd": {"Document.xml": b"<Document/>"}, "fzz": {"part.fz": b"<module fritzingVersion='1'/>"},
        "epro": {"project.esch": b"{}"}, "pptx": {"ppt/presentation.xml": b"<p:presentation/>"},
        "odp": {"mimetype": b"application/vnd.oasis.opendocument.presentation", "content.xml": b"<office/>"}}
    if extension in containers:
        return archive(containers[extension])
    if extension == "zip":
        return archive({"board.gtl": sample("gtl", "gerber")}) if subtype == "gerber" else archive({"README.txt": b"fixture"})
    if extension in {"tgz", "tar.gz"}:
        return gzip.compress(b"structural tar/ODB placeholder (not a real export)")
    if extension in {"xml", "cvg"}:
        return b'<IPC-2581 revision="C"><Content/></IPC-2581>'
    if extension == "kicad_pro":
        return json.dumps({"meta": {"version": 1}, "boards": []}).encode()
    if extension == "json":
        return b'{"head":{"docType":"3","editorVersion":"6.5"}}'
    if extension == "schdoc":
        return b"|HEADER=Protel for Windows - Schematic Capture Ascii File Version 5.0\n"
    if extension == "prjpcb":
        return b"[Design]\nVersion=1\n"
    if extension == "asc":
        text = "Version 4\nSHEET 1 880 680\nWIRE 0 0 1 1\n"
        return b"\xff\xfe" + text.encode("utf-16le") if subtype == "utf16le" else text.encode()
    if extension == "csv":
        return b"Ref,Val,Package,PosX,PosY\nR1,10k,0603,1,2\n" if subtype == "pickplace" else b"Reference,Value,Footprint\nR1,10k,0603\n"
    if extension == "pos":
        return b"### Module positions - created on fixture\n# Ref Val Package PosX PosY Rot Side\n"
    if extension == "elf":
        return elf({"arm": 40, "avr": 83, "xtensa": 94, "riscv": 243}[subtype])
    binaries = {"bgcode": b"GCDE" + struct.pack("<I", 1) + b"\0" * 10,
        "uf2": uf2(), "pes": b"#PES0001" + b"\0" * 8, "dst": b"LA:fixture".ljust(512, b" ") + b"\0\0\xf3",
        "jef": struct.pack("<I", 116) + b"\0" * 120, "vp3": b"%vsm%" + b"\0" * 20,
        "7z": b"7z\xbc\xaf\x27\x1c\0\x04" + b"\0" * 24,
        "mp4": struct.pack(">I", 24) + b"ftypisom" + b"\0" * 20,
        "mov": struct.pack(">I", 24) + b"ftypqt  " + b"\0" * 20,
        "webm": b"\x1a\x45\xdf\xa3" + b"\0" * 20, "mkv": b"\x1a\x45\xdf\xa3" + b"\0" * 20,
        "hex": b":0100000001FE\n:00000001FF\n", "obj": b"v 0 0 0\nv 1 0 0\nf 1 2 1\n",
        "mtl": b"newmtl sample\nKd 1 1 1\n", "scad": b"cube([1,1,1]);\n"}
    return binaries[extension]


SAMPLES = {}


def _fixtures(exts, subtypes):
    for ext in exts.split():
        for subtype in subtypes.split():
            SAMPLES[ext, subtype] = partial(sample, ext, subtype)


for exts, subtypes in [
    ("svg", "svg"), ("dxf", "ascii binary"), ("ai", "pdf postscript"), ("eps", "ascii dos"),
    ("pdf", "pdf"), ("lbrn lbrn2", "lightburn"), ("studio3", "opaque"), ("cdr", "riff zip"),
    ("stl", "binary ascii"), ("3mf gcode.3mf", "core prusa bambu orca sliced"), ("obj", "obj"),
    ("mtl", "mtl"), ("amf", "xml zip"), ("ply", "ascii little big"), ("gcode gco g nc tap ngc cnc", "gcode"),
    ("bgcode", "bgcode"), ("crv crv3d", "opaque"), ("step stp", "step"), ("stpz", "gzip"),
    ("iges igs", "iges"), ("f3d", "zip opaque"), ("sldprt sldasm slddrw ipt iam", "ole2"),
    ("skp", "sketchup"), ("fcstd", "freecad"), ("scad", "scad"), ("blend", "plain gzip zstd"),
    ("dwg", "dwg"), ("3dm", "rhino"), ("drl xln", "excellon"), ("zip", "gerber archive source"),
    ("tgz", "odb gzip"), ("xml cvg", "ipc2581"), ("kicad_pcb", "kicad_pcb"), ("kicad_sch", "kicad_sch"),
    ("kicad_sym", "kicad_symbol_lib"), ("kicad_mod", "footprint module"), ("kicad_pro", "kicad_project"),
    ("sch", "kicad5 eagle"), ("pro lib", "kicad5"), ("brd lbr", "eagle"), ("pcbdoc schdoc", "ole2"),
    ("schdoc", "ascii"), ("prjpcb", "altium_project"), ("json epro", "easyeda"), ("fzz", "fritzing"),
    ("asc", "utf8 utf16le"), ("csv", "bom pickplace"), ("pos", "positions"), ("ino py c h cpp hpp cc", "source"),
    ("hex", "intelhex"), ("bin", "opaque"), ("uf2", "uf2"), ("elf", "arm avr xtensa riscv"),
    ("pes", "pes"), ("dst", "dst"), ("jef", "jef"), ("exp", "opaque"), ("vp3", "vp3"), ("tar.gz", "gzip"),
    ("7z", "7z"), ("mp4 mov", "isobmff"), ("webm mkv", "ebml"), ("pptx", "pptx"), ("odp", "odp"),
    ("jpg", "jpg"), ("jpeg", "jpeg"), ("png", "png"), ("webp", "webp")]:
    _fixtures(exts, subtypes)
_fixtures("gbr ger gtl gbl gts gbs gto gbo gtp gbp gko gm1 " + " ".join(f"g{i}" for i in range(1, 31)), "gerber")

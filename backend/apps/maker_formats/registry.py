"""Closed extension/subtype registry for hackathon-maker-v1 (MiB caps)."""
from dataclasses import dataclass
import unicodedata
import re

from .errors import FormatError

MIB = 1024 * 1024
POLICY_NAME = "hackathon-maker-v1"
POLICY_VERSION = 1


@dataclass(frozen=True)
class FormatSpec:
    extension: str
    subtype: str
    group: str
    max_bytes: int
    canonical_mime: str
    checker: str
    preview: str = "download"
    confidence: str = "structural"
    mime_aliases: tuple[str, ...] = ()

    @property
    def download_only(self):
        return self.preview == "download"


REGISTRY = {}


def _add(exts, subtypes, group, cap, mime, checker, preview="download", *, opaque=False,
         aliases=()):
    for ext in exts.split():
        for subtype in subtypes.split():
            REGISTRY[ext, subtype] = FormatSpec(
                ext, subtype, group, cap * MIB, mime, checker, preview,
                "opaque-real-export-required" if opaque else "structural", tuple(aliases),
            )


_add("svg", "svg", "fab-2d", 10, "image/svg+xml", "xml", "image")
_add("dxf", "ascii binary", "fab-2d", 50, "image/vnd.dxf", "binary",
     aliases=("application/dxf", "application/x-dxf"))
_add("ai", "pdf postscript", "fab-2d", 100, "application/postscript", "binary", aliases=("application/pdf",))
_add("eps", "ascii dos", "fab-2d", 50, "application/postscript", "binary")
_add("pdf", "pdf", "fab-2d", 50, "application/pdf", "binary", "pdf")
_add("lbrn lbrn2", "lightburn", "fab-2d", 50, "application/xml", "xml")
_add("studio3", "opaque", "fab-2d", 50, "application/octet-stream", "binary", opaque=True)
_add("cdr", "riff zip", "fab-2d", 100, "application/vnd.corel-draw", "binary", opaque=True)
_add("stl", "binary ascii", "fab-3dprint", 200, "model/stl", "binary", "mesh",
     aliases=("application/sla", "application/vnd.ms-pki.stl", "text/plain"))
_add("3mf gcode.3mf", "core prusa bambu orca sliced", "fab-3dprint", 200,
     "model/3mf", "zip", "mesh", aliases=(
         "application/vnd.ms-package.3dmanufacturing-3dmodel+xml", "application/vnd.ms-3mfdocument"))
_add("obj", "obj", "fab-3dprint", 200, "model/obj", "text", "mesh")
_add("mtl", "mtl", "fab-3dprint", 1, "model/mtl", "text")
_add("amf", "xml zip", "fab-3dprint", 100, "model/amf", "xml",
     aliases=("application/x-amf", "application/xml", "text/xml"))
_add("ply", "ascii little big", "fab-3dprint", 200, "model/ply", "binary",
     aliases=("application/x-ply", "text/plain"))
_add("gcode gco g", "gcode", "fab-3dprint", 500, "text/x.gcode", "text", "text",
     aliases=("application/x-gcode",))
_add("bgcode", "bgcode", "fab-3dprint", 200, "application/x-bgcode", "binary")
_add("nc tap ngc cnc", "gcode", "fab-cnc", 200, "text/x.gcode", "text", "text")
_add("crv crv3d", "opaque", "fab-cnc", 200, "application/octet-stream", "binary", opaque=True)
_add("step stp", "step", "hardware-cad", 200, "model/step", "text", "brep",
     aliases=("application/step",))
_add("stpz", "gzip", "hardware-cad", 200, "application/gzip", "binary")
_add("iges igs", "iges", "hardware-cad", 200, "model/iges", "text", "brep",
     aliases=("application/iges",))
_add("f3d", "zip opaque", "hardware-cad", 200, "application/octet-stream", "binary", opaque=True)
_add("sldprt sldasm slddrw ipt iam", "ole2", "hardware-cad", 200,
     "application/octet-stream", "binary", opaque=True)
_add("skp", "sketchup", "hardware-cad", 200, "application/vnd.sketchup.skp", "binary", opaque=True)
_add("fcstd", "freecad", "hardware-cad", 200, "application/zip", "zip")
_add("scad", "scad", "hardware-cad", 5, "text/plain", "text", "text")
_add("blend", "plain gzip zstd", "hardware-cad", 200, "application/x-blender", "binary", opaque=True)
_add("dwg", "dwg", "hardware-cad", 100, "image/vnd.dwg", "binary")
_add("3dm", "rhino", "hardware-cad", 200, "model/vnd.3dm", "binary")
GERBER_EXTENSIONS = "gbr ger gtl gbl gts gbs gto gbo gtp gbp gko gm1 " + " ".join(
    f"g{i}" for i in range(1, 31))
_add(GERBER_EXTENSIONS, "gerber", "hardware-pcb", 20, "application/vnd.gerber", "text", "gerber")
_add("drl xln", "excellon", "hardware-pcb", 10, "application/x-excellon", "text", "gerber")
_add("zip", "gerber", "hardware-pcb", 50, "application/zip", "zip", "gerber")
_add("tgz", "odb", "hardware-pcb", 100, "application/gzip", "binary")
_add("xml cvg", "ipc2581", "hardware-pcb", 100, "application/xml", "xml")
for ext, subtype, cap in (("kicad_pcb", "kicad_pcb", 25), ("kicad_sch", "kicad_sch", 25),
                          ("kicad_sym", "kicad_symbol_lib", 10), ("kicad_mod", "footprint", 5),
                          ("kicad_mod", "module", 5)):
    _add(ext, subtype, "hardware-pcb", cap, "text/plain", "text", aliases=(f"application/x-{ext.replace('_', '-')}",))
_add("kicad_pro", "kicad_project", "hardware-pcb", 1, "application/json", "text")
_add("sch", "kicad5 eagle", "hardware-pcb", 25, "text/plain", "text",
     aliases=("application/xml", "text/xml"))
_add("pro lib", "kicad5", "hardware-pcb", 25, "text/plain", "text")
_add("brd lbr", "eagle", "hardware-pcb", 25, "application/xml", "xml")
_add("pcbdoc schdoc", "ole2", "hardware-pcb", 50, "application/octet-stream", "binary")
_add("schdoc", "ascii", "hardware-pcb", 50, "text/plain", "text")
_add("prjpcb", "altium_project", "hardware-pcb", 1, "text/plain", "text")
_add("json", "easyeda", "hardware-pcb", 20, "application/json", "text")
_add("epro", "easyeda", "hardware-pcb", 50, "application/zip", "zip")
_add("fzz", "fritzing", "hardware-pcb", 50, "application/zip", "zip")
_add("asc", "utf8 utf16le", "hardware-pcb", 5, "text/plain", "text", "text")
_add("csv", "bom pickplace", "hardware-pcb", 5, "text/csv", "text", "table")
_add("pos", "positions", "hardware-pcb", 5, "text/plain", "text", "table")
_add("ino py c h cpp hpp cc", "source", "firmware", 1, "text/plain", "text", "text",
     aliases=("text/x-python", "text/x-c", "text/x-c++src", "text/x-c++hdr", "text/x-chdr"))
_add("hex", "intelhex", "firmware", 16, "text/x-hex", "text", "text")
_add("bin", "opaque", "firmware", 16, "application/octet-stream", "binary", opaque=True)
_add("uf2", "uf2", "firmware", 32, "application/x-uf2", "binary")
_add("elf", "arm avr xtensa riscv", "firmware", 32, "application/x-elf", "binary")
for ext, subtype in (("pes", "pes"), ("dst", "dst"), ("jef", "jef"),
                      ("exp", "opaque"), ("vp3", "vp3")):
    _add(ext, subtype, "embroidery", 10, "application/octet-stream", "binary", opaque=True)
_add("zip", "archive", "archives", 200, "application/zip", "zip", "listing")
_add("zip", "source", "source", 200, "application/zip", "zip", "listing")
_add("tar.gz tgz", "gzip", "archives", 200, "application/gzip", "binary")
_add("7z", "7z", "archives", 200, "application/x-7z-compressed", "binary")
_add("mp4 mov", "isobmff", "video", 500, "video/mp4", "binary", "video",
     aliases=("video/quicktime",))
_add("webm mkv", "ebml", "video", 500, "video/webm", "binary", "video",
     aliases=("video/x-matroska",))
_add("pptx", "pptx", "deck", 50,
     "application/vnd.openxmlformats-officedocument.presentationml.presentation", "zip")
_add("odp", "odp", "deck", 50, "application/vnd.oasis.opendocument.presentation", "zip")
for ext, mime in (("jpg", "jpeg"), ("jpeg", "jpeg"), ("png", "png"), ("webp", "webp")):
    _add(ext, ext, "images", 5, f"image/{mime}", "image", "image")


def extension_from_name(filename):
    """Strict display names: no paths, controls or normalization tricks."""
    if not isinstance(filename, str) or not 1 <= len(filename) <= 240:
        raise FormatError("invalid_filename")
    if unicodedata.normalize("NFKC", filename) != filename or filename != filename.strip():
        raise FormatError("invalid_filename")
    if any(unicodedata.category(c).startswith("C") for c in filename):
        raise FormatError("invalid_filename")
    if re.search(r"[/\\:]", filename) or filename.startswith(".") or filename.endswith("."):
        raise FormatError("invalid_filename")
    value = filename.lower()
    for suffix in ("gcode.3mf", "tar.gz"):
        if value.endswith("." + suffix):
            return suffix
    return value.rsplit(".", 1)[-1] if "." in value else ""


def resolve_spec(filename, *, group, subtype, declared_mime, event_cap=None):
    spec = REGISTRY.get((extension_from_name(filename), subtype))
    if spec is None or spec.group != group:
        raise FormatError("unsupported_format")
    mimes = {spec.canonical_mime, *spec.mime_aliases, "application/octet-stream"}
    if spec.checker in {"text", "xml"}:
        mimes.add("text/plain")
    if declared_mime not in mimes:
        raise FormatError("mime_mismatch")
    if event_cap is not None and (type(event_cap) is not int or event_cap < 1):
        raise FormatError("invalid_cap")
    return spec, min(spec.max_bytes, event_cap or spec.max_bytes)

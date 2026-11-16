"""Strict validation entry point: metadata only, no code or toolpath execution."""
from dataclasses import dataclass
import re

from .errors import FormatError
from .signatures_binary import check_binary
from .signatures_text import check_text
from .signatures_xml import check_xml
from .signatures_zip import check_zip


@dataclass(frozen=True)
class ValidationResult:
    mime: str
    subtype: str
    preview: str
    manifest: tuple = ()


def validate(reader, spec, *, effective_cap=None):
    cap = min(effective_cap or spec.max_bytes, spec.max_bytes)
    if type(reader.size) is not int or reader.size < 1:
        raise FormatError("empty_file")
    if reader.size > cap:
        raise FormatError("file_too_large", 413)
    prefix = reader.read(0, min(8192, reader.size)).lstrip()
    forbidden = (b"MZ", b"\xcf\xfa\xed\xfe", b"\xce\xfa\xed\xfe", b"\xfe\xed\xfa\xcf",
                 b"\xfe\xed\xfa\xce", b"\xca\xfe\xba\xbe")
    if prefix.startswith(forbidden) or (prefix.startswith(b"\x7fELF") and spec.extension != "elf"):
        raise FormatError("executable_disguise")
    if prefix.startswith(b"#!") and not (spec.extension == "py" and spec.subtype == "source"
                                         and re.match(br"#![^\n]*\bpython(?:3(?:\.\d+)?)?(?:\s|$)", prefix.split(b"\n")[0])):
        raise FormatError("executable_disguise")
    if re.match(br"(?is)(?:<html\b|<!doctype\s+html\b|<script\b|<\?php\b)", prefix):
        raise FormatError("active_content_disguise")
    signatures = ((b"%PDF-", {"pdf", "ai"}), (b"\x89PNG\r\n\x1a\n", {"png"}),
        (b"\xff\xd8\xff", {"jpg", "jpeg"}), (b"7z\xbc\xaf\x27\x1c", {"7z"}),
        (b"BLENDER", {"blend"}), (b"3D Geometry File Format ", {"3dm"}),
        (b"\xff\xfe\xff\x0e", {"skp"}), (b"UF2\nWQ]\x9e", {"uf2"}),
        (b"\x1a\x45\xdf\xa3", {"webm", "mkv"}))
    for magic, permitted in signatures:
        if prefix.startswith(magic) and spec.extension not in permitted:
            raise FormatError("signature_disguise")
    if prefix.startswith(b"PK\x03\x04") and spec.checker != "zip" and spec.subtype != "zip":
        raise FormatError("signature_disguise")
    if prefix.startswith(b"\x1f\x8b") and spec.extension not in {"stpz", "blend", "tar.gz", "tgz"}:
        raise FormatError("signature_disguise")
    manifest = ()
    if spec.checker == "zip" or spec.subtype == "zip":
        manifest = check_zip(reader, spec)
    elif spec.checker == "xml":
        check_xml(reader, spec)
    elif spec.checker == "text":
        check_text(reader, spec)
    elif spec.checker == "image":
        from .images import canonical_image
        canonical_image(b"".join(reader.chunks()), expected_mime=spec.canonical_mime)
    else:
        check_binary(reader, spec)
    mime = "application/pdf" if spec.extension == "ai" and spec.subtype == "pdf" else spec.canonical_mime
    if spec.extension == "sch" and spec.subtype == "eagle":
        mime = "application/xml"
    if spec.extension == "mov":
        mime = "video/quicktime"
    if spec.extension == "mkv":
        mime = "video/x-matroska"
    return ValidationResult(mime, spec.subtype, spec.preview, tuple(manifest or ()))

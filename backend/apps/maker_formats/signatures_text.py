"""Strict incremental Unicode validation, inert content-only format checks."""
import codecs
import csv
import io
import json
import re

from .errors import FormatError


def text_prefix(reader, spec):
    decoder = codecs.getincrementaldecoder("utf-16" if spec.subtype == "utf16le" else "utf-8-sig")()
    prefix, remaining = [], 1024 * 1024
    try:
        for chunk in reader.chunks(65536):
            value = decoder.decode(chunk)
            if "\x00" in value:
                raise FormatError("invalid_text")
            if remaining:
                prefix.append(value[:remaining])
                remaining -= min(remaining, len(value))
        if "\x00" in decoder.decode(b"", final=True):
            raise FormatError("invalid_text")
    except UnicodeError as exc:
        raise FormatError("invalid_text") from exc
    return "".join(prefix)


def _intelhex(reader):
    buffer, eof = b"", False
    for chunk in reader.chunks(65536):
        buffer += chunk
        lines = buffer.split(b"\n")
        buffer = lines.pop()
        if len(buffer) > 600:
            raise FormatError("invalid_hex")
        for line in lines:
            eof = _hexline(line.strip(), eof)
    if buffer.strip():
        eof = _hexline(buffer.strip(), eof)
    if not eof:
        raise FormatError("invalid_hex")


def _hexline(line, eof):
    if not line:
        return eof
    try:
        if eof or not line.startswith(b":") or len(line) > 521:
            raise ValueError()
        record = bytes.fromhex(line[1:].decode("ascii"))
        if len(record) != record[0] + 5 or sum(record) % 256:
            raise ValueError()
        if record[3] not in range(6):
            raise ValueError()
        if record[3] == 1 and record != b"\x00\x00\x00\x01\xff":
            raise ValueError()
        return record[3] == 1
    except (UnicodeError, ValueError, IndexError) as exc:
        raise FormatError("invalid_hex") from exc


def check_text(reader, spec):
    if spec.subtype == "eagle":
        from .signatures_xml import check_xml
        return check_xml(reader, spec)
    if spec.subtype == "utf16le" and reader.read(0, min(2, reader.size)) != b"\xff\xfe":
        raise FormatError("invalid_text")
    prefix = text_prefix(reader, spec)
    subtype = spec.subtype
    valid = False
    if subtype == "gcode":
        clean = re.sub(r"\([^)]*\)|;[^\n]*", "", prefix)
        valid = bool(re.search(r"(?m)^\s*(?:N\d+\s*)?[GM]\d+(?:\s|$|[XYZEFST])", clean))
    elif subtype == "step":
        valid = prefix.lstrip().startswith("ISO-10303-21;")
    elif subtype == "iges":
        lines = prefix.splitlines()
        valid = bool(lines) and all(len(v) == 80 for v in lines[:8]) and lines[0][72] == "S"
    elif subtype in {"obj", "mtl"}:
        valid = bool(re.search(r"(?m)^v\s+[-+.\d]+\s+[-+.\d]+\s+[-+.\d]+" if subtype == "obj"
                               else r"(?m)^newmtl\s+\S+", prefix))
    elif subtype == "gerber":
        valid = "*" in prefix and bool(re.search(r"%FS|%MO|^(?:G04|%TF)", prefix))
    elif subtype == "excellon":
        clean = re.sub(r"(?m)^;[^\n]*", "", prefix).lstrip()
        valid = clean.startswith("M48") and bool(re.search(r"(?m)^M30\s*$", prefix))
    elif subtype in {"kicad_pcb", "kicad_sch", "kicad_symbol_lib", "footprint", "module"}:
        valid = prefix.lstrip().startswith("(" + subtype + " ")
    elif subtype == "kicad5":
        expected = {"sch": "EESchema Schematic File Version", "lib": "EESchema-LIBRARY Version",
                    "pro": "["}[spec.extension]
        valid = prefix.startswith(expected)
    elif subtype in {"kicad_project", "easyeda"}:
        try:
            data = json.loads(b"".join(reader.chunks()))
            valid = isinstance(data, dict) and (
                ("meta" in data and any(k in data for k in ("board", "boards", "schematic")))
                if subtype == "kicad_project" else
                ("head" in data and isinstance(data["head"], dict) and "docType" in data["head"]
                 or "editorVersion" in data))
        except (ValueError, UnicodeError, RecursionError):
            valid = False
    elif subtype == "ascii" and spec.extension == "schdoc":
        valid = prefix.startswith("|HEADER=Protel for Windows")
    elif subtype == "altium_project":
        valid = prefix.startswith("[Design]")
    elif spec.extension == "asc":
        valid = prefix.startswith("Version 4") and bool(re.search(r"(?m)^SHEET\s+\d", prefix))
    elif subtype in {"bom", "pickplace"}:
        try:
            rows = csv.reader(io.StringIO(prefix), dialect=csv.Sniffer().sniff(prefix[:8192], delimiters=",;\t"))
            header = {v.strip().lower() for v in next(rows)}
            valid = (bool(header & {"reference", "ref", "designator"}) and
                     bool(header & {"value", "val", "comment"}))
            if subtype == "pickplace":
                valid &= bool(header & {"posx", "mid x", "x"}) and bool(header & {"posy", "mid y", "y"})
        except (csv.Error, StopIteration):
            valid = False
    elif subtype == "positions":
        valid = prefix.startswith("### Module positions")
    elif subtype == "intelhex":
        _intelhex(reader)
        valid = True
    elif subtype in {"source", "scad"}:
        valid = bool(prefix.strip())
    if not valid:
        raise FormatError("text_subtype_mismatch")

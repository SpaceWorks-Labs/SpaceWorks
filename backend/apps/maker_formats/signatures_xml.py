"""Incremental XML checks across the entire object, never a prefix-only proof."""
import re
import codecs
from xml.etree.ElementTree import XMLPullParser, ParseError

from .errors import FormatError

EAGLE_DTD = re.compile(br'<!DOCTYPE\s+eagle\s+SYSTEM\s+[\'"]eagle\.dtd[\'"]\s*>', re.I)


def check_xml(reader, spec):
    parser = XMLPullParser(events=("start", "end"))
    decoder = codecs.getincrementaldecoder("utf-8")()
    root, previous, count, depth = None, b"", 0, 0
    expected = {"svg": "svg", "lightburn": "LightBurnProject", "xml": "amf",
                "ipc2581": "IPC-2581", "eagle": "eagle"}[spec.subtype]
    try:
        for chunk in reader.chunks(65536):
            # Only UTF-8 is accepted. This also excludes UTF-16 declaration bypasses.
            if b"\x00" in chunk:
                raise FormatError("unsafe_xml")
            combined = previous + chunk
            lowered = combined.lower()
            if b"<!entity" in lowered:
                raise FormatError("unsafe_xml")
            scrubbed = EAGLE_DTD.sub(b"", combined) if spec.subtype == "eagle" else combined
            if re.search(br"<!doctype", scrubbed, re.I):
                # Retain incomplete declaration until its closing > has arrived.
                at = re.search(br"<!doctype", scrubbed, re.I).start()
                if b">" in scrubbed[at:] or len(scrubbed) - at > 256:
                    raise FormatError("unsafe_xml")
            previous = combined[-512:]
            parser.feed(decoder.decode(chunk))
            for event, element in parser.read_events():
                if event == "end":
                    depth -= 1
                    element.clear()
                    continue
                count, depth = count + 1, depth + 1
                if count > 1_000_000 or depth > 64:
                    raise FormatError("xml_limit", 413)
                local = element.tag.rsplit("}", 1)[-1]
                root = root or local
                if root != expected:
                    raise FormatError("xml_subtype_mismatch")
                if spec.subtype == "svg":
                    if local.lower() in {"script", "foreignobject", "style", "iframe", "object", "embed"}:
                        raise FormatError("unsafe_svg")
                    for key, value in element.attrib.items():
                        attr = key.rsplit("}", 1)[-1].lower()
                        normalized = re.sub(r"\s", "", value).lower()
                        if (attr.startswith("on") or "javascript:" in normalized or
                                "url(" in normalized or "\\" in normalized or
                                (attr in {"href", "src"} and not value.startswith("#"))):
                            raise FormatError("unsafe_svg")
        if re.search(br"<!doctype", EAGLE_DTD.sub(b"", previous), re.I):
            raise FormatError("unsafe_xml")
        parser.feed(decoder.decode(b"", final=True))
        parser.close()
    except (ParseError, UnicodeError) as exc:
        raise FormatError("invalid_xml") from exc
    if root != expected or depth != 0:
        raise FormatError("invalid_xml")

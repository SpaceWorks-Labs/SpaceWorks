"""Real booking/arrival fixtures and PDF stream inspection for BK-G."""
import base64
import re
import zlib
from datetime import timedelta

from django.utils import timezone

from apps.bookings.services_arrival import confirm_arrival, qr_value
from tests.bookings.staff_grant_helpers import client_for
from tests.bookings.test_staff_tools_helpers import world


def pass_world(monkeypatch, permission="check_in", arrived=True):
    w = world(monkeypatch, permission=permission)
    w.tenant.enabled_features += ["bookings.confirmations", "bookings.checkin", "bookings.passes"]
    w.tenant.save(update_fields=["enabled_features"])
    if arrived:
        monkeypatch.setattr(timezone, "now", lambda: w.row.starts_at - timedelta(minutes=10))
        w.row = confirm_arrival(w.resource, qr_value(w.row), actor=w.actor)
    w.owner = client_for(w.member)
    w.print_url = f"/api/v1/admin/spaces/{w.resource.pk}/arrival/{w.row.pk}/pass/"
    w.template_url = f"/api/v1/admin/spaces/{w.resource.pk}/pass-template/"
    w.preview_url = f"/api/v1/admin/spaces/{w.resource.pk}/pass-preview/"
    w.member_url = f"/api/v1/public/{w.tenant.slug}/my-bookings/{w.row.public_token}/pass.pdf"
    return w


def pdf_content(payload):
    """Inspect actual decoded PDF streams, including ReportLab's ASCII85+Flate."""
    assert payload.startswith(b"%PDF-")
    parts = [payload]
    for stream in re.findall(rb"stream\r?\n(.*?)endstream", payload, re.S):
        stream = stream.strip()
        try:
            if stream.endswith(b"~>"):
                stream = base64.a85decode(stream, adobe=True)
            parts.append(zlib.decompress(stream))
        except (ValueError, zlib.error):
            parts.append(stream)
    return b"\n".join(parts)


def pdf_text(payload):
    """Decode drawn ReportLab text with each font's own ToUnicode subset map.

    Shaping may split a name into multiple Tj/TJ operations; raw stream bytes
    need not contain the original contiguous string. A CMap entry alone is not
    evidence that its glyph was actually drawn.
    """
    objects = {int(pk): body for pk, body in re.findall(
        rb"(\d+) 0 obj\s*(.*?)\s*endobj", payload, re.S)}
    maps = {}
    for pk, body in objects.items():
        reference = re.search(rb"/ToUnicode\s+(\d+) 0 R", body)
        if reference:
            cmap = pdf_content(b"%PDF-\n" + objects[int(reference[1])])
            maps[pk] = {
                int(code, 16): bytes.fromhex(value.decode()).decode("utf-16-be")
                for block in re.findall(rb"beginbfchar(.*?)endbfchar", cmap, re.S)
                for code, value in re.findall(rb"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>", block)
            }
    fonts = {name: maps[int(pk)] for name, pk in re.findall(
        rb"/([^\s/]+)\s+(\d+) 0 R", payload) if int(pk) in maps}
    literal = rb"\(((?:\\[\s\S]|[^\\()])*)\)"
    operators = re.compile(rb"/([^\s/]+)\s+[\d.]+\s+Tf|" + literal + rb"\s*Tj|\[(.*?)\]\s*TJ", re.S)
    drawn = []
    for body in objects.values():
        if b"stream" not in body or b"/ToUnicode" in body:
            continue
        stream = pdf_content(b"%PDF-\n" + body).split(b"endstream", 1)[-1]
        font = {}
        for match in operators.finditer(stream):
            if match[1]:
                font = fonts.get(match[1], {})
                continue
            chunks = [match[2]] if match[2] is not None else re.findall(literal, match[3])
            for chunk in chunks:
                raw = re.sub(rb"\\([0-7]{1,3}|[\s\S])", _pdf_escape, chunk)
                drawn.append("".join(font.get(code, chr(code)) for code in raw))
        drawn.append("\n")
    return "".join(drawn)


def _pdf_escape(match):
    value = match[1]
    if value.isdigit():
        return bytes([int(value, 8)])
    return {b"n": b"\n", b"r": b"\r", b"t": b"\t", b"b": b"\b", b"f": b"\f",
            b"\n": b"", b"\r": b""}.get(value, value)

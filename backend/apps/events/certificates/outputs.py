"""Certificate outputs beyond the PDF (C7, C8): a 300 dpi PNG and a 1200 x 627 share image.

The PNG is the issued PDF rasterised by pdfium (the card designer's helper), so the two never
disagree. The share image carries no QR code and prints the holder's name only when the
holder chose to show it.
"""
import hashlib
from io import BytesIO

from django.conf import settings

from apps.events.certificate_storage import CertificateStorageUnavailable, _client
from .merge import frozen_merge, kind_title

SHARE_DPI = 150
SHARE_MM = (1200 * 25.4 / SHARE_DPI, 627 * 25.4 / SHARE_DPI)  # 203.2 x 106.17 mm -> 1200 x 627 px.
MAX_PDF = 20 * 1024 * 1024


def stored_pdf(row):
    """The immutable issued PDF, checked against its recorded SHA-256."""
    from botocore.exceptions import BotoCoreError, ClientError
    try:
        response = _client(settings.AWS_S3_ENDPOINT_URL).get_object(
            Bucket=settings.AWS_STORAGE_BUCKET_NAME, Key=row.object_key)
        with response["Body"] as body:
            content = body.read(MAX_PDF + 1)
    except (BotoCoreError, ClientError, OSError) as exc:
        raise CertificateStorageUnavailable() from exc
    if len(content) > MAX_PDF or hashlib.sha256(content).hexdigest() != row.sha256:
        raise CertificateStorageUnavailable("The certificate failed its checksum check.")
    return content


def certificate_png(row):
    from apps.card_designs.raster import pdf_page_to_png
    return pdf_page_to_png(stored_pdf(row), 0, dpi=300)


def _text(text, box, size, *, colour, weight=500, family="Gilroy", align="left"):
    x, y, width, height = box
    return {"id": "00000000-0000-4000-8000-000000000000", "order": 0, "type": "text", "x_mm": x, "y_mm": y,
            "width_mm": width, "height_mm": height, "rotation": 0, "text": text, "font_family": family,
            "font_weight": weight, "font_size_pt": size, "align": align, "shrink_to_fit": True,
            "line_height": 1.15, "tracking_pt": 0, "colour": colour, "uppercase": False}


def share_image(row, *, status=None):
    """1200 x 627 PNG for social posts and link previews (no QR; name only when opted in)."""
    from reportlab.lib.units import mm
    from reportlab.pdfgen.canvas import Canvas
    from apps.card_designs.raster import pdf_page_to_png
    from .layout import COLOURS
    from .text_rendering import draw_text
    width, height = SHARE_MM
    merge = frozen_merge(row)
    buffer = BytesIO()
    canvas = Canvas(buffer, pagesize=(width * mm, height * mm), invariant=1)
    canvas.setFillColor(COLOURS["ink"])
    canvas.rect(0, 0, width * mm, height * mm, fill=1, stroke=0)
    canvas.setFillColor(COLOURS["citron"])
    canvas.rect(0, 0, 3 * mm, height * mm, fill=1, stroke=0)
    _seal(canvas, cx=width - 30, cy=height / 2, revoked=(status or row.status) == "revoked")
    lines = [(row.issuer_name, (12, 10, 150, 8), 12, COLOURS["sky"], 600, "Gilroy"),
             (kind_title(row.kind), (12, 22, 150, 16), 24, COLOURS["cream"], 600, "Unbounded")]
    top = 42
    if merge.get("award"):
        lines.append((merge["award"], (12, top, 150, 9), 15, COLOURS["citron"], 600, "Gilroy"))
        top += 11
    if getattr(row, "holder_name_public", False):
        lines.append((row.recipient_name, (12, top, 150, 14), 26, COLOURS["cream"], 700, "Gilroy"))
        top += 16
    lines.append((row.event_title, (12, top, 150, 10), 15, COLOURS["cream"], 500, "Gilroy"))
    lines.append((merge_date(row), (12, top + 11, 150, 7), 11, COLOURS["cream"], 400, "Gilroy"))
    footer = "Revoked certificate" if (status or row.status) == "revoked" else "Verify this certificate"
    lines.append((f"{footer} · ID {str(row.serial)[:8].upper()}", (12, height - 14, 150, 7), 10, COLOURS["sky"], 500, "Gilroy"))
    for text, box, size, colour, weight, family in lines:
        if text:
            draw_text(canvas, text, _text(text, box, size, colour=colour, weight=weight, family=family), height)
    canvas.showPage()
    canvas.save()
    return pdf_page_to_png(buffer.getvalue(), 0, dpi=SHARE_DPI)


def merge_date(row):
    from zoneinfo import ZoneInfo
    zone = ZoneInfo(getattr(row, "event_timezone_name", "UTC") or "UTC")
    moment = row.event_starts_at.astimezone(zone)
    return f"{moment.day} {moment:%B %Y}"


def _seal(canvas, *, cx, cy, revoked):
    """A brand-coloured seal on the right: a check for a valid certificate, a cross once revoked."""
    from reportlab.lib.units import mm
    from .layout import COLOURS
    colour = COLOURS["orange"] if revoked else COLOURS["citron"]
    canvas.setStrokeColor(colour)
    canvas.setLineWidth(2.2)
    canvas.circle(cx * mm, cy * mm, 20 * mm, stroke=1, fill=0)
    canvas.setLineWidth(0.8)
    canvas.circle(cx * mm, cy * mm, 16.5 * mm, stroke=1, fill=0)
    canvas.setLineWidth(3.2)
    canvas.setLineCap(1)
    if revoked:
        canvas.line((cx - 6) * mm, (cy - 6) * mm, (cx + 6) * mm, (cy + 6) * mm)
        canvas.line((cx - 6) * mm, (cy + 6) * mm, (cx + 6) * mm, (cy - 6) * mm)
    else:
        path = canvas.beginPath()
        path.moveTo((cx - 7.5) * mm, (cy + 0.5) * mm)
        path.lineTo((cx - 2) * mm, (cy - 5.5) * mm)
        path.lineTo((cx + 8) * mm, (cy + 6) * mm)
        canvas.drawPath(path, stroke=1, fill=0)

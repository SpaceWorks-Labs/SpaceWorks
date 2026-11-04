"""Deterministic rendering exclusively from the immutable issuance snapshot."""

from io import BytesIO

from apps.events.certificate_rendering_legacy import render_legacy_certificate_pdf
from apps.operations.printable_pdf import text_box


def validate_certificate_layout(certificate):
    """Fit issuance text before freezing it, without storage I/O under DB locks."""
    from reportlab.pdfgen.canvas import Canvas

    if certificate.layout_snapshot:
        if certificate.layout_snapshot.get("version") == 2:
            from .certificates.rendering import render_layers
            render_layers(Canvas(BytesIO()), certificate, preflight=True)
            return
        _draw_text(Canvas(BytesIO()), certificate)


def render_certificate_pdf(certificate):
    # Migration leaves historical snapshots empty. Their immutable PDF keys may
    # already be promoted, so retries must reproduce the original Vera bytes.
    if not certificate.layout_snapshot:
        return render_legacy_certificate_pdf(certificate)

    from reportlab.lib.units import mm
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfgen.canvas import Canvas
    from apps.events.certificate_artwork_storage import read_artwork

    snapshot = certificate.layout_snapshot
    width, height = snapshot["page_width_mm"], snapshot["page_height_mm"]
    output = BytesIO()
    canvas = Canvas(output, pagesize=(width * mm, height * mm), pageCompression=1, invariant=1)
    canvas.setTitle(f"Attendance certificate {certificate.serial}")
    if snapshot.get("version") == 2:
        from .certificates.rendering import render_layers
        render_layers(canvas, certificate)
        canvas.showPage()
        canvas.save()
        return output.getvalue()
    key = snapshot.get("artwork_object_key")
    if key:
        payload = read_artwork(key, snapshot.get("artwork_version_id", ""), snapshot["artwork_sha256"])
        canvas.drawImage(ImageReader(BytesIO(payload)), 0, 0, width=width * mm, height=height * mm)
    else:
        canvas.rect(12 * mm, 12 * mm, (width - 24) * mm, (height - 24) * mm)
    _draw_text(canvas, certificate)
    canvas.showPage()
    canvas.save()
    return output.getvalue()


def _draw_text(canvas, certificate):
    # Preflight and PDF rendering must fit exactly the same frozen text/boxes.
    snapshot = certificate.layout_snapshot
    width, height = snapshot["page_width_mm"], snapshot["page_height_mm"]
    if not snapshot.get("artwork_object_key"):
        labels = (("Certificate of Attendance", 34, 28, True),
                  ("This certifies that", 57, 14, False),
                  ("attended", 101, 14, False), (certificate.event_title, 117, 20, True),
                  (certificate.event_starts_at.strftime("%d %B %Y"), 138, 13, False),
                  (certificate.issuer_name, 167, 12, False),
                  (f"Serial {certificate.serial} / Revision {certificate.revision}", 181, 8, False))
        for value, y, size, bold in labels:
            element = {"field": "label", "x_mm": width * 0.075, "y_mm": y * height / 210,
                       "width_mm": width * 0.85, "height_mm": height * 0.07,
                       "font": "sans", "font_size_pt": size, "bold": bold,
                       "align": "center", "colour": "#0F172A"}
            text_box(canvas, value, element, area_height_mm=height)
    text_box(canvas, certificate.recipient_name, snapshot["name_box"], area_height_mm=height)

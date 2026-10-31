"""Deterministic branded PDF for immutable ledger snapshots and live bill status."""

from functools import partial
from io import BytesIO
import logging

MAX_PDF_BYTES = 5 * 1024 * 1024
logger = logging.getLogger(__name__)


class DocumentRenderError(RuntimeError):
    pass


def render_document_pdf(document):
    if not 1 <= len(document.lines) <= 200:
        raise DocumentRenderError("A document supports between 1 and 200 lines.")
    from apps.operations.printable_text_fonts import FontScope
    with FontScope():
        result = _render(document)
    if len(result) > MAX_PDF_BYTES:
        logger.error("payment_document_pdf_too_large", extra={"document_id": document.pk, "size": len(result)})
        raise DocumentRenderError("Document PDF exceeds the delivery size limit.")
    return result


def _render(document):
    from reportlab.lib import colors
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate, Spacer, Table, TableStyle, Image
    from reportlab.pdfgen.canvas import Canvas
    from apps.operations.printable_pdf import document_paragraph
    from apps.makerspaces.theme_validation import HEX_COLOR
    from .document_pdf_assets import load_logo
    from .document_snapshot import bill_status, local_date, payment_navigation, DEFAULT_ACCENT
    from . import document_pdf_tax as tax

    issuer = document.issuer
    accent = issuer.get("accent_color", DEFAULT_ACCENT)
    accent = accent if isinstance(accent, str) and HEX_COLOR.fullmatch(accent) else DEFAULT_ACCENT
    accent = colors.HexColor(accent)
    style = ParagraphStyle("document", fontSize=9, leading=14, textColor=colors.HexColor("#142C2A"))
    heading = ParagraphStyle("heading", parent=style, fontSize=23, leading=30, spaceAfter=8)
    small = ParagraphStyle("small", parent=style, fontSize=8, leading=12, textColor=colors.HexColor("#5B6863"))
    total_style = ParagraphStyle("total", parent=style, fontSize=16, leading=22)
    def text(value, selected=style, bold=False):
        return document_paragraph(str(value), selected, bold=bold)

    story = []
    logo = load_logo(document)
    if logo:
        image = Image(BytesIO(logo))
        ratio = min(45 * mm / image.imageWidth, 22 * mm / image.imageHeight)
        image.drawWidth, image.drawHeight = image.imageWidth * ratio, image.imageHeight * ratio
        story.extend([image, Spacer(1, 4 * mm)])
    story.extend([text(issuer["name"], heading, True), text(issuer.get("address", ""))])
    for label, key in (("Issuer identifier", "tax_id"), ("Contact", "contact_email")):
        if issuer.get(key):
            story.append(text(f"{label}: {issuer[key]}", small))
    breakdown = document.tax_breakdown
    for label, value in (tax.identity_lines(breakdown) if breakdown else ()):
        story.append(text(f"{label}: {value}", small))
    story.extend([Spacer(1, 7 * mm), text(tax.tax_title(document) if breakdown else document.get_kind_display(), heading, True),
        text(document.number, bold=True), text(f"Issued {local_date(document, document.issued_at)}", small)])
    if document.kind == "bill":
        story.append(text(bill_status(document), bold=True))
    story.extend([Spacer(1, 5 * mm), text(f"Bill to: {document.payer_label}"), Spacer(1, 5 * mm)])
    rows = [[text(label, small, True) for label in ("Description", "Qty", "Unit", "Total")]]
    rows.extend([[text(line["label"]), text(line["quantity"]), text(line["unit_amount"]), text(line["total"])]
                 for line in document.lines])
    table = Table(rows, colWidths=[94 * mm, 16 * mm, 30 * mm, 30 * mm], repeatRows=1, hAlign="LEFT")
    table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5), ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#FFF4E8")),
        ("LINEBELOW", (0, 0), (-1, 0), 1.5, accent),
        ("LINEBELOW", (0, 1), (-1, -1), 0.3, colors.HexColor("#EFE6DB")),
    ]))
    totals = Table([[text("Total", bold=True), text(f"{document.currency.upper()} {document.amount}", total_style, True)]],
                   colWidths=[22 * mm, 58 * mm], hAlign="RIGHT")
    totals.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#FFF4E8")),
        ("BOX", (0, 0), (-1, -1), 1, accent), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 10), ("BOTTOMPADDING", (0, 0), (-1, -1), 10)]))
    story.extend([table, Spacer(1, 6 * mm), totals, Spacer(1, 5 * mm)])
    if breakdown:
        tax_table = Table([[text(label, small), text(value, small, True)] for label, value in tax.summary_rows(document)],
                          colWidths=[50 * mm, 40 * mm], hAlign="RIGHT")
        tax_table.setStyle(TableStyle([("LINEBELOW", (0, 0), (-1, -1), 0.3, colors.HexColor("#EFE6DB"))]))
        story.extend([tax_table, Spacer(1, 5 * mm)])
    details = []
    if document.kind == "bill":
        details.extend([text(f"Due {local_date(document, issuer.get('due_at'))}"), text("How to pay", bold=True)])
        if issuer.get("payment_instructions"):
            details.append(text(issuer["payment_instructions"]))
        if issuer.get("tax_note"):
            details.append(text(issuer["tax_note"], small))
        # Financial details stay frozen; navigation follows the current tenant.
        from .models import Payment
        payment = Payment.objects.select_related("makerspace", "via_makerspace").get(pk=document.payment_id)
        navigation = payment_navigation(payment)
        if navigation:
            details.append(text(f"Sign in to view this charge: {navigation}", small))
        from .availability import online_payments_enabled_for
        # The URL is authenticated navigation, never a stored provider checkout bearer.
        if payment.status == "pending" and online_payments_enabled_for(payment):
            details.append(text("Pay online from your signed-in payments page.", small))
    else:
        details.extend([text(f"Money date: {local_date(document, document.money_at)}", small),
                        text(f"Method: {tax.method_text(document)}", small),
                        text(f"Reference: {document.settlement_reference or '-'}", small)])
        if document.reverses_id:
            details.append(text(f"Reverses {document.reverses.number}", small))
        elif document.kind == "credit_note" and issuer.get("receipt_number"):
            details.append(text(f"Refund against receipt {issuer['receipt_number']}", small))
    story.extend(details)
    notes = tax.footer_notes(document) if breakdown else ["Gross-only. No tax calculation is included."]
    story.extend([Spacer(1, 7 * mm), *(text(note, small) for note in notes), text(issuer.get("footer", ""), small)])
    output = BytesIO()
    def page_footer(canvas, pdf):
        canvas.setStrokeColor(accent)
        canvas.line(20 * mm, 18 * mm, 190 * mm, 18 * mm)
        footer = text(f"{document.number} - Page {pdf.page}", small)
        footer.wrap(170 * mm, 10 * mm)
        footer.drawOn(canvas, 20 * mm, 11 * mm)
    SimpleDocTemplate(output, invariant=1, rightMargin=20 * mm, leftMargin=20 * mm, topMargin=18 * mm,
                      bottomMargin=23 * mm, title=document.number, pageCompression=1).build(
        story, onFirstPage=page_footer, onLaterPages=page_footer, canvasmaker=partial(Canvas, invariant=1))
    return output.getvalue()

"""Paginated registry PDF export with provenance and bounded, wrapping cells."""

from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape


def render_pdf(rows, *, provenance, title):
    import reportlab
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, LongTable, TableStyle

    fonts = Path(reportlab.__file__).parent / "fonts"
    if "ReportVera" not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont("ReportVera", str(fonts / "Vera.ttf")))
    style = ParagraphStyle("report", fontName="ReportVera", fontSize=9, leading=13, wordWrap="CJK")
    def paragraph(value):
        return Paragraph(escape(str(value if value is not None else "")), style)
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=40, rightMargin=40,
                            topMargin=40, bottomMargin=40, title=title)
    story = [paragraph(title), Spacer(1, 12)]
    for key, value in provenance.items():
        story.append(paragraph(f"{key}: {value}"))
    # Transpose each aggregate record into a readable metric/value table; wide
    # report-registry schemas never overflow the page horizontally.
    for index, row in enumerate(rows[1:], 1):
        story.extend([Spacer(1, 14), paragraph(f"Record {index}")])
        table = LongTable([[paragraph(key.replace("_", " ")), paragraph(value)]
                           for key, value in zip(rows[0], row, strict=True)], colWidths=[180, 330])
        table.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"),
                                   ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                                   ("LINEBELOW", (0, 0), (-1, -1), .3, colors.HexColor("#d7dce2"))]))
        story.append(table)
    def footer(canvas, document):
        canvas.setFont("ReportVera", 8)
        canvas.drawRightString(A4[0] - 40, 22, f"Page {document.page}")
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return buffer.getvalue()

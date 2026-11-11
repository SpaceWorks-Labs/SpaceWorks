"""Paginated registry PDF export with provenance and bounded, wrapping cells."""

from io import BytesIO
from xml.sax.saxutils import escape

from django.utils.translation import gettext


def render_pdf(rows, *, provenance, title):
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, LongTable, TableStyle

    from .report_pdf_fonts import report_font_name
    font = report_font_name()
    style = ParagraphStyle("report", fontName=font, fontSize=9, leading=13, wordWrap="CJK")
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
    def table(pairs, label=lambda key: key.replace("_", " ")):
        built = LongTable([[paragraph(label(key)), paragraph(value)] for key, value in pairs], colWidths=[180, 330])
        built.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"),
                                   ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                                   ("LINEBELOW", (0, 0), (-1, -1), .3, colors.HexColor("#d7dce2"))]))
        return built

    for index, row in enumerate(rows[1:], 1):
        story.extend([Spacer(1, 14), paragraph(f"Record {index}")])
        pairs = list(zip(rows[0], row, strict=True))
        # Parity C19: the event report appends `money_*` and `spending_*` columns only when the viewer may see
        # money; they print as their own Money and Spending sections instead of two more rows of the table.
        main = [pair for pair in pairs if not pair[0].startswith(("money_", "spending_"))]
        story.append(table(main))
        for heading, prefix in ((gettext("Money"), "money_"), (gettext("Spending"), "spending_")):
            section = [pair for pair in pairs if pair[0].startswith(prefix)]
            if section:
                story.extend([Spacer(1, 10), paragraph(heading),
                              table(section, label=lambda key, prefix=prefix: key[len(prefix):].replace("_", " "))])
    def footer(canvas, document):
        canvas.setFont(font, 8)
        canvas.drawRightString(A4[0] - 40, 22, f"Page {document.page}")
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return buffer.getvalue()

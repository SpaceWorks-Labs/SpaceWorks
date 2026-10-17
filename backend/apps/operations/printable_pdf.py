"""Already-authorized text -> bounded ReportLab boxes; no domain model imports."""

from io import BytesIO
import unicodedata

from rest_framework.exceptions import ValidationError

from .printable_fonts import font_markup, font_runs


def document_paragraph(text, style, *, bold=False):
    """The document path shapes font runs separately, including mixed-script words.

    Both printable surfaces share the coverage/cluster selection in font_markup;
    the flowable retains logical cluster text for extraction and accessibility.
    """
    from .printable_paragraph import UnicodeParagraph
    font_markup(str(text), "sans", bold, logical=True)
    return UnicodeParagraph(text, style, bold=bold)


def text_box(canvas, text, element, *, origin_x=0, origin_y=0, area_height_mm):
    from reportlab.lib.colors import HexColor
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph

    if len(str(text)) > 500:
        raise ValidationError({"layout": "Printable text exceeds 500 characters."})
    width, height = element["width_mm"] * mm, element["height_mm"] * mm
    text = str(text or "-")
    rtl = any(unicodedata.bidirectional(char) in ("R", "AL") for char in text)
    # ReportLab shapes a whole word with its first font. With mixed-font words
    # it can paint a glyph from the wrong cmap. Keep native widths for those
    # words; single-font complex-script words still shape.
    shaping = all(len(font_runs(word, element["font"], element["bold"])) <= 1
                  for word in text.split())
    size = element["font_size_pt"]
    # Shrink within the supported range, then refuse instead of silently losing text.
    while size >= 6:
        style = ParagraphStyle("print", fontName=f'Print-sans-{element["bold"]}',
                               fontSize=size, leading=size * 1.3, shaping=shaping,
                               alignment={"left": 0, "center": 1, "right": 2}[element["align"]],
                               textColor=HexColor(element["colour"]), splitLongWords=True)
        markup = (rtl_markup(text, element, style, width) if rtl else
                  font_markup(text, element["font"], element["bold"]))
        if markup is not None:
            paragraph = Paragraph(markup, style)
            _width, needed = paragraph.wrap(width, height)
            if needed <= height and _line_widths_fit(paragraph):
                x = origin_x + element["x_mm"] * mm
                y = origin_y + (area_height_mm - element["y_mm"]) * mm - needed
                canvas.saveState()
                path = canvas.beginPath()
                path.rect(x, origin_y + (area_height_mm - element["y_mm"]) * mm - height, width, height)
                canvas.clipPath(path, stroke=0)
                paragraph.drawOn(canvas, x, y)
                canvas.restoreState()
                return
        if size == 6:
            break
        size = max(6, size - 0.5)
    raise ValidationError({"layout": "Text does not fit. Enlarge its box or shorten the selected field."})


def _line_widths_fit(paragraph):
    """ReportLab may place an unsplittable glyph wider than its wrap width.

    Both plain and styled line representations record the unused width in
    extraSpace; a negative value means the actual text extends past the box.
    Paragraph.wrap() itself returns the requested width even in that case.
    """
    lines = paragraph.blPara
    return all((line[0] if lines.kind == 0 else line.extraSpace) >= -1e-6
               for line in lines.lines)


def rtl_markup(text, element, style, width):
    """Wrap logical words first, then apply bidi within each final display line.

    Reordering an entire paragraph before wrapping reverses the order of its
    lines. Overlong unbreakable words shrink with the containing box instead.
    """
    from reportlab.platypus import Paragraph
    lines, current = [], ""
    def markup(value):
        return font_markup(value, element["font"], element["bold"])
    def fits(value):
        paragraph = Paragraph(markup(value), style)
        _width, height = paragraph.wrap(width, 100000)
        return height <= style.leading + 0.01 and _line_widths_fit(paragraph)
    for word in text.split():
        candidate = f"{current} {word}".strip()
        if fits(candidate):
            current = candidate
        else:
            if not current or not fits(word):
                return None
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return "<br/>".join(markup(line) for line in lines)


def render_sheet(template, rows, *, title, layout):
    from reportlab.lib.units import mm
    from reportlab.pdfgen.canvas import Canvas

    page_width, page_height, columns, count_rows = layout(template)
    output = BytesIO()
    canvas = Canvas(output, pagesize=(page_width * mm, page_height * mm),
                    pageCompression=1, invariant=1)
    canvas.setTitle(title)
    per_page = columns * count_rows
    for index, values in enumerate(rows):
        slot = index % per_page
        if index and slot == 0:
            canvas.showPage()
        x = (template["margin_mm"] + (slot % columns)
             * (template["card_width_mm"] + template["gap_mm"])) * mm
        y = (page_height - template["margin_mm"] - (slot // columns + 1)
             * template["card_height_mm"] - (slot // columns) * template["gap_mm"]) * mm
        canvas.rect(x, y, template["card_width_mm"] * mm, template["card_height_mm"] * mm)
        for element in template["elements"]:
            text_box(canvas, values[element["field"]], element, origin_x=x, origin_y=y,
                     area_height_mm=template["card_height_mm"])
    canvas.showPage()
    canvas.save()
    return output.getvalue()

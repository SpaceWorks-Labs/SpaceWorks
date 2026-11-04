"""Build-time proof that the image can render every supported printable script."""

from io import BytesIO
import shutil
import sys

from apps.operations.printable_fonts import BUNDLED_FONT_ROOT, font_paths, font_markup, register_fonts
from apps.operations.printable_text_fonts import FontScope
from apps.operations.printable_paragraph import UnicodeParagraph


def verify(*, bundle=False):
    if bundle:
        BUNDLED_FONT_ROOT.mkdir(parents=True, exist_ok=True)
        for filename, source in font_paths().items():
            target = BUNDLED_FONT_ROOT / filename
            if source != target:
                shutil.copyfile(source, target)
        font_paths.cache_clear()
    register_fonts()
    # Exercise dependencies as well as font presence: shaping and visual bidi are
    # part of printable correctness, including when the test source is mounted.
    import uharfbuzz  # noqa: F401
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.pdfgen.canvas import Canvas
    from reportlab.platypus import Paragraph

    output = BytesIO()
    canvas = Canvas(output)
    y = 750
    for text in ("Zo\u00eb Fran\u00e7ois", "\u05e9\u05dc\u05d5\u05dd", "\u0645\u0631\u062d\u0628\u0627", "\u0928\u092e\u0938\u094d\u0924\u0947", "\u4e2d\u6587"):
        for bold in (False, True):
            paragraph = Paragraph(font_markup(text, "sans", bold), ParagraphStyle(
                "smoke", fontName=f"Print-sans-{bold}", fontSize=12, leading=16, shaping=1,
            ))
            paragraph.wrap(400, 30)
            paragraph.drawOn(canvas, 30, y)
            y -= 30
    canvas.save()
    if not output.getvalue().startswith(b"%PDF-"):
        raise RuntimeError("Printable runtime did not produce a PDF.")
    # Fail the build if the billing mixed-run/embedded-subset path is unavailable.
    output = BytesIO()
    with FontScope():
        canvas = Canvas(output, invariant=1)
        for index, value in enumerate(("Latin Ελληνικά Кириллица", "العربية हिन्दी বাংলা தமிழ்",
                "ខ្មែរ မြန်မာ ລາວ ไทย සිංහල", "中文 繁體 日本語 한국어", "עברית 123 Latin")):
            paragraph = UnicodeParagraph(value, ParagraphStyle("billing", fontSize=10, leading=14))
            paragraph.wrap(450, 100)
            paragraph.drawOn(canvas, 30, 750 - index * 50)
        canvas.save()
    if not output.getvalue().startswith(b"%PDF-"):
        raise RuntimeError("Billing font runtime did not produce a PDF.")


if __name__ == "__main__":
    verify(bundle="--bundle" in sys.argv[1:])

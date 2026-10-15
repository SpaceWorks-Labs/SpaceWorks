"""Unicode report font, independent of every separable domain."""

import os
from pathlib import Path


def report_font_name():
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    name = "ReportUnicode"
    if name not in pdfmetrics.getRegisteredFontNames():
        # fonts-dejavu-core is installed by the backend image. ReportLab resolves
        # the filename through its cross-platform TTFSearchPath. Native Windows
        # QA uses the OS font without redistributing any proprietary font bytes.
        font = "DejaVuSans.ttf"
        windows = os.environ.get("WINDIR") or os.environ.get("SystemRoot")
        if os.name == "nt" and windows:
            font = str(Path(windows) / "Fonts" / "arial.ttf")
        pdfmetrics.registerFont(TTFont(name, font))
    return name

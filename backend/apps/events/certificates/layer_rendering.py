"""Deterministic typed-resource rendering. No URL or merge tag can fetch an image."""

from django.utils.translation import gettext
from dataclasses import dataclass, field
from io import BytesIO
import hashlib

from rest_framework.exceptions import ValidationError
from .layout import COLOURS
from .text_rendering import draw_text


@dataclass(frozen=True)
class ImageResource:
    content: bytes = field(repr=False)
    sha256: str

    def __post_init__(self):
        if hashlib.sha256(self.content).hexdigest() != self.sha256:
            raise ValidationError({"resource": gettext("The immutable image checksum changed.")})


@dataclass(frozen=True)
class QrResource:
    payload: str = field(repr=False)
    dummy: bool = False


@dataclass(frozen=True)
class SignatureResource:
    """A frozen signatory: printed name and title, plus the checksum-pinned image (or none)."""
    name: str = field(repr=False)
    title: str = field(repr=False)
    image: ImageResource | None = None


def draw_document(canvas, document, values, resolver, *, preview=False):
    from reportlab.lib.units import mm
    from reportlab.lib.utils import ImageReader
    height = document["page_height_mm"]
    for layer in document["layers"]:
        if layer.get("hidden"):
            continue
        canvas.saveState()
        try:
            cx = (layer["x_mm"] + layer["width_mm"] / 2) * mm
            cy = (height - layer["y_mm"] - layer["height_mm"] / 2) * mm
            canvas.translate(cx, cy)
            canvas.rotate(-layer["rotation"])
            canvas.translate(-cx, -cy)
            canvas.setFillAlpha(layer.get("opacity", 1))
            kind = layer["type"]
            if kind in ("text", "certificate_id"):
                text = str(values.get("certificate_id", "SAMPLE")) if kind == "certificate_id" else layer["text"]
                for tag, value in values.items():
                    text = text.replace("{{" + tag + "}}", str(value))
                draw_text(canvas, text, layer, height)
                continue
            resource = resolver(layer)
            if kind == "signature":
                from .signature_rendering import draw_signature
                draw_signature(canvas, layer, resource, height)
                continue
            x, y = layer["x_mm"] * mm, (height-layer["y_mm"]-layer["height_mm"]) * mm
            width, box_height = layer["width_mm"] * mm, layer["height_mm"] * mm
            if isinstance(resource, QrResource):
                _qr(canvas, resource, x, y, width, box_height, preview=preview)
            elif isinstance(resource, ImageResource):
                canvas.drawImage(ImageReader(BytesIO(resource.content)), x, y, width=width, height=box_height,
                                 preserveAspectRatio=True, anchor="c", mask="auto")
            elif kind == "photo":
                _initials(canvas, layer, values, x, y, width, box_height, height)
            elif resource is not None:
                raise ValidationError({"resource": gettext("Wrong resource type for layer.")})
        finally:
            canvas.restoreState()


def _qr(canvas, resource, x, y, width, height, *, preview):
    from reportlab.graphics.barcode.qr import QrCodeWidget
    from reportlab.graphics.shapes import Drawing
    from reportlab.graphics import renderPDF
    side = min(width, height)
    canvas.setFillColorRGB(1, 1, 1)
    canvas.rect(x, y, width, height, fill=1, stroke=0)
    if preview or resource.dummy:
        canvas.setFillColor(COLOURS["ink"])
        for i in range(7):
            for j in range(7):
                if (i+j) % 3 == 0:
                    canvas.rect(x+i*side/7, y+j*side/7, side/9, side/9, fill=1, stroke=0)
        return
    qr = QrCodeWidget(resource.payload, barLevel="M", barBorder=4)
    a, b, c, d = qr.getBounds()
    drawing = Drawing(side, side, transform=[side/(c-a), 0, 0, side/(d-b), 0, 0])
    drawing.add(qr)
    renderPDF.draw(drawing, canvas, x+(width-side)/2, y+(height-side)/2)


PLACEHOLDER = "#D7E9E5"  # Reads on light and dark cards alike; the card engine uses the same tint.


def _initials(canvas, layer, values, x, y, width, box_height, page_height):
    """No other profile is fetched as a fallback: a tinted box with the authorized initials, centred."""
    from reportlab.lib.colors import HexColor
    canvas.setFillColor(HexColor(PLACEHOLDER))
    canvas.rect(x, y, width, box_height, fill=1, stroke=0)
    initials = "".join(word[:1] for word in values.get("name", "").split()[:2]).upper()
    if not initials:
        return
    side_mm = min(layer["width_mm"], layer["height_mm"])
    size = max(6, min(96, side_mm * 72 / 25.4 / 2.2))
    line_mm = size * 1.1 * 25.4 / 72
    draw_text(canvas, initials, {**layer, "type": "text", "font_family": "Gilroy", "font_weight": 700,
                                 "font_size_pt": size, "align": "center", "colour_token": "ink", "colour": COLOURS["ink"],
                                 "line_height": 1.1, "tracking_pt": 0, "shrink_to_fit": True, "uppercase": False,
                                 "y_mm": layer["y_mm"] + max(0, (layer["height_mm"] - line_mm) / 2),
                                 "height_mm": min(layer["height_mm"], line_mm + 0.01)}, page_height)

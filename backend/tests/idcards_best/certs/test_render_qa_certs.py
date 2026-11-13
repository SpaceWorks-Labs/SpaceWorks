"""LOCAL render QA for the certificate parts: kind/award tags, signatures, portrait pages and
share images, written to tests/idcards_best/out/ for a human to look at."""
import hashlib
from io import BytesIO
from types import SimpleNamespace
from uuid import uuid4

import pytest
from django.utils import timezone

from tests.idcards_best.test_render_qa import NAMES, OUT, _montage, _save


def _text(order, text, box, size, *, weight=500, family="Gilroy", align="center", colour="ink"):
    return {"id": str(uuid4()), "order": order, "type": "text", "x_mm": box[0], "y_mm": box[1], "width_mm": box[2],
            "height_mm": box[3], "rotation": 0, "text": text, "font_family": family, "font_weight": weight,
            "font_size_pt": size, "align": align, "shrink_to_fit": True, "colour_token": colour, "line_height": 1.2}


def _document(width, height):
    margin = width * 0.08
    inner = width - 2 * margin
    layers = [
        _text(0, "{{kind}} certificate", (margin, height * 0.12, inner, 16), 26, weight=600, family="Unbounded"),
        _text(1, "This certifies that", (margin, height * 0.24, inner, 8), 12),
        _text(2, "{{name}}", (margin, height * 0.30, inner, 20), 32, weight=700),
        _text(3, "{{award}}", (margin, height * 0.42, inner, 10), 15, weight=600, colour="teal"),
        _text(4, "{{role}} · {{event}} · {{eventDate}}", (margin, height * 0.49, inner, 10), 13),
    ]
    sig_w = min(60, inner / 3 - 6)
    for slot in (1, 2, 3):
        x = margin + (slot - 1) * (inner / 3) + (inner / 3 - sig_w) / 2
        layers.append({"id": str(uuid4()), "order": len(layers), "type": "signature", "signature_slot": slot,
                       "x_mm": x, "y_mm": height * 0.62, "width_mm": sig_w, "height_mm": 30, "rotation": 0,
                       "font_size_pt": 10, "font_weight": 600, "align": "center", "colour_token": "ink"})
    layers.append({"id": str(uuid4()), "order": len(layers), "type": "certificate_qr", "x_mm": width - 33,
                   "y_mm": height - 33, "width_mm": 25, "height_mm": 25, "rotation": 0,
                   "resource_slot": "certificate_verification_qr"})
    layers.append({"id": str(uuid4()), "order": len(layers), "type": "certificate_id", "x_mm": 8, "y_mm": height - 12,
                   "width_mm": width - 48, "height_mm": 7, "rotation": 0, "font_size_pt": 7, "align": "left"})
    return {"version": 2, "page_width_mm": width, "page_height_mm": height, "layers": layers}


def _signature_png():
    from PIL import Image, ImageDraw
    image = Image.new("RGBA", (600, 200), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.line([(30, 150), (120, 60), (200, 140), (300, 50), (420, 150), (560, 80)], fill="#142C2A", width=8)
    buffer = BytesIO()
    image.save(buffer, "PNG")
    return buffer.getvalue()


@pytest.mark.django_db
def test_render_certificate_kinds_signatures_and_pages():
    from reportlab.lib.units import mm
    from reportlab.pdfgen.canvas import Canvas
    from apps.card_designs.raster import pdf_page_to_png
    from apps.events.certificates.layout import normalize_document
    from apps.events.certificates.layer_rendering import ImageResource, QrResource, SignatureResource, draw_document
    from apps.events.certificates.merge import sample_merge
    signature = _signature_png()
    people = {1: ("Dr Meera Krishnan", "Director"), 2: ("Alexandra Montgomery-Fitzgerald", "Programme lead"),
              3: ("محمد عبد الله", "Partner")}
    files = []
    for page, (width, height) in {"a4-landscape": (297, 210), "a4-portrait": (210, 297),
                                  "letter-portrait": (215.9, 279.4)}.items():
        document = normalize_document(_document(width, height))
        for kind, name in (("winner", "short"), ("organiser_thanks", "long"), ("mentor_thanks", "malayalam")):
            merge = sample_merge(kind)
            values = {"name": NAMES[name], "event": "Community Hardware Hackathon 2026", "eventDate": "18 October 2026",
                      "organisation": "Tinkerspace", "issueDate": "20 October 2026",
                      "certificate_id": "6f1c2a9e-1b2c-4d5e-8f90-123456789abc", **merge, "crewRole": merge["role"]}

            def resource(layer):
                if layer["type"] == "certificate_qr":
                    return QrResource("https://spaceworks.example/certificates/verify/" + "a" * 32)
                if layer["type"] == "signature":
                    who, title = people[layer["signature_slot"]]
                    image = ImageResource(signature, hashlib.sha256(signature).hexdigest()) if layer["signature_slot"] != 3 else None
                    return SignatureResource(who, title, image)
                return None
            buffer = BytesIO()
            canvas = Canvas(buffer, pagesize=(width * mm, height * mm))
            draw_document(canvas, document, values, resource)
            canvas.showPage()
            canvas.save()
            fname = f"certkind-{page}-{kind}-{name}.png"
            _save(fname, pdf_page_to_png(buffer.getvalue(), 0, dpi=80))
            files.append(fname)
    _montage(files, "MONTAGE-cert-kinds.png", columns=3, scale=0.8)


@pytest.mark.django_db
def test_render_share_images():
    from apps.events.certificates.outputs import share_image
    files = []
    for kind, name, show in (("winner", "short", True), ("attendance", "long", True), ("mentor_thanks", "malayalam", True),
                             ("participant", "arabic", True), ("organiser_thanks", "long", False)):
        row = SimpleNamespace(issuer_name="Thiruvananthapuram Community Makerspace", kind=kind, status="active",
                              layout_snapshot={"merge": {"award": "1st place · Best hardware hack" if kind == "winner" else ""}},
                              holder_name_public=show, recipient_name=NAMES[name], award_id=None,
                              event_title="Community Hardware Hackathon 2026", event_timezone_name="Asia/Kolkata",
                              event_starts_at=timezone.now(), serial=uuid4())
        fname = f"share-{kind}-{name}{'' if show else '-hidden'}.png"
        _save(fname, share_image(row))
        files.append(fname)
    _montage(files, "MONTAGE-share.png", columns=2, scale=0.6)
    assert (OUT / files[0]).exists()

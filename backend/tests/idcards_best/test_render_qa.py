"""LOCAL render QA (never committed): renders every card template and certificate seed to
PNG/PDF under $IDCARDS_QA_OUT (default: the system temp dir) so a human can look at them. Asserts only that
rendering succeeds; the visual check is manual."""
import os
import tempfile
from io import BytesIO
from pathlib import Path

import pytest

# The test tree can be read-only (the CI runner mounts it for another user), so output goes to a temp dir.
OUT = Path(os.environ.get("IDCARDS_QA_OUT") or Path(tempfile.gettempdir()) / "spaceworks-idcards-best-out")
NAMES = {
    "short": "Priya Raman",
    "long": "Alexandra Montgomery-Fitzgerald",
    "malayalam": "അനന്തകൃഷ്ണൻ നായർ",
    "devanagari": "प्रियंका शर्मा",
    "arabic": "محمد عبد الله",
    "cjk": "李小龙",
}


def _photo():
    from PIL import Image, ImageDraw
    image = Image.new("RGB", (600, 800), "#7A9CC6")
    draw = ImageDraw.Draw(image)
    draw.ellipse((170, 140, 430, 440), fill="#E8B894")
    draw.rectangle((120, 470, 480, 800), fill="#2B4C7E")
    draw.ellipse((120, 430, 480, 640), fill="#2B4C7E")
    buffer = BytesIO()
    image.save(buffer, "JPEG")
    return buffer.getvalue()


def _logo(colour="#E4572E"):
    from PIL import Image, ImageDraw
    image = Image.new("RGBA", (400, 400), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((20, 20, 380, 380), 80, fill=colour)
    draw.ellipse((120, 120, 280, 280), fill="white")
    buffer = BytesIO()
    image.save(buffer, "PNG")
    return buffer.getvalue()


def _context(name, *, photo=True, preview=False, long=False):
    from apps.card_designs.data_fields import SAMPLE_LONG, SAMPLE_SHORT
    from apps.card_designs.rendering import RenderContext
    values = dict(SAMPLE_LONG if long else SAMPLE_SHORT)
    values["name"] = name
    values["verify_url"] = "spaceworks.example/verify/c/Abc123"
    return RenderContext(values=values, desk_qr="0123456789abcdef0123456789abcdef",
                         verify_qr="https://spaceworks.example/verify/c/" + "A" * 43,
                         photo=_photo() if photo else None,
                         logos={"space": _logo(), "organisation": _logo("#3A7D44"), "event": _logo("#6B4C9A")},
                         preview=preview)


def _save(name, data):
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_bytes(data)


def _montage(files, target, columns=3, scale=0.5):
    from PIL import Image, ImageDraw
    images = [Image.open(OUT / f).convert("RGB") for f in files]
    images = [im.resize((int(im.width * scale), int(im.height * scale))) for im in images]
    cw = max(im.width for im in images) + 20
    ch = max(im.height for im in images) + 40
    rows = (len(images) + columns - 1) // columns
    sheet = Image.new("RGB", (cw * columns, ch * rows), "#888888")
    draw = ImageDraw.Draw(sheet)
    for i, (im, f) in enumerate(zip(images, files)):
        r, c = divmod(i, columns)
        sheet.paste(im, (c * cw + 10, r * ch + 30))
        draw.text((c * cw + 10, r * ch + 8), f, fill="black")
    sheet.save(OUT / target)


@pytest.mark.django_db
def test_render_card_templates():
    from apps.card_designs.default_templates import TEMPLATES, build
    from apps.card_designs.layout import normalize_document, sides
    from apps.card_designs.rendering import render_pdf, render_png
    domains = {"member": "member_cards", "programme": "id_programme", "event": "event_card"}
    themes = [None]
    try:
        from apps.card_designs.default_templates import THEMES
        themes = list(THEMES)
    except ImportError:
        pass
    for theme in themes:
        for dkey, domain in domains.items():
            files = []
            for key in TEMPLATES:
                doc = build(key, domain) if theme is None else build(key, domain, theme=theme)
                doc = normalize_document(doc)
                for nkey in ("short", "long"):
                    ctx = _context(NAMES[nkey], long=nkey == "long")
                    for side in sides(doc):
                        fname = f"card-{theme or 'base'}-{dkey}-{key}-{nkey}-{side}.png"
                        _save(fname, render_png(doc, ctx, side=side))
                        files.append(fname)
                _save(f"card-{theme or 'base'}-{dkey}-{key}.pdf", render_pdf(doc, _context(NAMES["short"])))
            _montage(files, f"MONTAGE-{theme or 'base'}-{dkey}.png", columns=4, scale=0.45)


@pytest.mark.django_db
def test_render_scripts_and_fallbacks():
    from apps.card_designs.default_templates import build
    from apps.card_designs.layout import normalize_document
    from apps.card_designs.rendering import render_png
    files = []
    for key in ("classic", "event_pass", "student"):
        doc = normalize_document(build(key, "member_cards" if key != "event_pass" else "event_card"))
        for nkey in ("malayalam", "devanagari", "arabic", "cjk"):
            fname = f"script-{key}-{nkey}.png"
            _save(fname, render_png(doc, _context(NAMES[nkey])))
            files.append(fname)
        fname = f"nophoto-{key}.png"
        _save(fname, render_png(doc, _context("Priya Raman", photo=False)))
        files.append(fname)
        mono = dict(doc, mono=True)
        fname = f"mono-{key}.png"
        _save(fname, render_png(mono, _context("Priya Raman")))
        files.append(fname)
    _montage(files, "MONTAGE-scripts.png", columns=3, scale=0.45)


@pytest.mark.django_db
def test_render_sheet():
    from apps.card_designs.default_templates import build
    from apps.card_designs.layout import normalize_document
    from apps.card_designs.raster import pdf_page_to_png
    from apps.card_designs.sheets import render_sheets
    doc = normalize_document(build("classic", "member_cards"))
    cards = [(doc, _context(NAMES[k])) for k in list(NAMES) * 2]
    pdf = render_sheets(cards, paper="a4", order="duplex")
    _save("sheet-a4.pdf", pdf)
    _save("sheet-a4-p1.png", pdf_page_to_png(pdf, 0, dpi=100))
    _save("sheet-a4-p2.png", pdf_page_to_png(pdf, 1, dpi=100))


@pytest.mark.django_db
def test_render_certificate_seeds():
    import hashlib
    from reportlab.lib.units import mm
    from reportlab.pdfgen.canvas import Canvas
    from apps.events.certificates.layer_rendering import ImageResource, QrResource, draw_document
    from apps.events.certificates.seed_artwork import render_packaged
    from apps.events.certificates.seeds import catalogue
    from apps.card_designs.raster import pdf_page_to_png
    files = []
    logo = _logo()
    for theme in ("light", "dark"):
        for seed in catalogue(kind="certificate", theme=theme):
            document = seed["document"]
            for nkey in ("short", "long", "malayalam", "arabic"):
                buffer = BytesIO()
                canvas = Canvas(buffer, pagesize=(document["page_width_mm"] * mm, document["page_height_mm"] * mm))

                def resource(layer, document=document):
                    if layer["type"] == "image":
                        content = render_packaged(layer["resource_id"], width_mm=document["page_width_mm"],
                                                  height_mm=document["page_height_mm"])
                        return ImageResource(content, hashlib.sha256(content).hexdigest())
                    if layer["type"] == "logo":
                        return ImageResource(logo, hashlib.sha256(logo).hexdigest())
                    if layer["type"] in ("certificate_qr",):
                        return QrResource("https://spaceworks.example/certificates/verify/" + "a" * 32)
                    return None

                draw_document(canvas, document, {
                    "name": NAMES[nkey], "event": "Community Hardware Hackathon 2026" if nkey == "long" else "Spring Build Night",
                    "eventDate": "18 October 2026", "organisation": "Tinkerspace", "issueDate": "20 October 2026",
                    "certificate_id": "6f1c2a9e-1b2c-4d5e-8f90-123456789abc", "crewRole": ""}, resource)
                canvas.showPage()
                canvas.save()
                fname = f"cert-{theme}-{seed['seed_id']}-{nkey}.png"
                _save(fname.replace(".png", ".pdf"), buffer.getvalue())
                _save(fname, pdf_page_to_png(buffer.getvalue(), 0, dpi=100))
                files.append(fname)
    _montage(files, "MONTAGE-certs.png", columns=4, scale=0.5)


@pytest.mark.django_db
def test_render_badge_seeds():
    import hashlib
    from reportlab.lib.units import mm
    from reportlab.pdfgen.canvas import Canvas
    from apps.events.certificates.layer_rendering import ImageResource, QrResource, draw_document
    from apps.events.certificates.seed_artwork import render_packaged
    from apps.events.certificates.seeds import catalogue
    from apps.card_designs.raster import pdf_page_to_png
    files = []
    for theme in ("light", "dark"):
        for stock in ("cr80-landscape", "a6-portrait"):
            for seed in catalogue(kind="badge", theme=theme, stock=stock):
                document = seed["document"]
                buffer = BytesIO()
                canvas = Canvas(buffer, pagesize=(document["page_width_mm"] * mm, document["page_height_mm"] * mm))

                def resource(layer, document=document):
                    if layer["type"] == "image":
                        content = render_packaged(layer["resource_id"], width_mm=document["page_width_mm"],
                                                  height_mm=document["page_height_mm"])
                        return ImageResource(content, hashlib.sha256(content).hexdigest())
                    if layer["type"] in ("event_credential_qr", "certificate_qr"):
                        return QrResource("TICKET-" + "x" * 30)
                    return None
                try:
                    draw_document(canvas, document, {"name": NAMES["long"], "event": "Spring Build Night",
                                                     "eventDate": "18 October 2026", "organisation": "Tinkerspace",
                                                     "issueDate": "20 October 2026", "certificate_id": "X"}, resource)
                except Exception as exc:  # noqa: BLE001
                    (OUT / f"badge-{theme}-{stock}-{seed['seed_id']}.err").write_text(repr(exc))
                    continue
                canvas.showPage()
                canvas.save()
                fname = f"badge-{theme}-{stock}-{seed['seed_id']}.png"
                _save(fname, pdf_page_to_png(buffer.getvalue(), 0, dpi=150))
                files.append(fname)
    if files:
        _montage(files, "MONTAGE-badges.png", columns=4, scale=0.5)

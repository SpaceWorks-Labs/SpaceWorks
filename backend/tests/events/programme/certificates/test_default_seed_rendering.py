"""Authoritative E rendering of every packaged family/theme/physical stock."""

from copy import deepcopy
from hashlib import sha256
from io import BytesIO

from PIL import Image
import pytest
from reportlab.pdfgen.canvas import Canvas
from reportlab.lib.units import mm
from rest_framework.exceptions import ValidationError

from apps.events.certificates import seeds
from apps.events.certificates.badge_designs import validate_design
from apps.events.certificates.layer_rendering import ImageResource, QrResource, draw_document
from apps.events.certificates.seed_artwork import render_packaged, packaged_resource
from apps.events.default_templates import CERTIFICATE_SEEDS, iter_badge_stock_seeds
from apps.events.programme_runtime import template_catalogue

ALL = [*CERTIFICATE_SEEDS, *iter_badge_stock_seeds()]


@pytest.mark.parametrize("seed", ALL, ids=lambda s: f"{s['seed_id']}-{s['theme']}-{s.get('stock', 'certificate')}")
@pytest.mark.parametrize("photo", [False, True])
def test_all_server_designs_render_physical_pdf_with_typed_resources(seed, photo, monkeypatch):
    monkeypatch.setattr(seeds, "_catalogue", template_catalogue)
    kind = "badge" if "stock" in seed else "certificate"
    installed = next(row for row in seeds.catalogue(kind=kind, theme=seed["theme"], stock=seed.get("stock"))
                     if row["seed_id"] == seed["seed_id"])
    document = installed["document"]
    background = render_packaged(seed["resources"][0]["id"], width_mm=document["page_width_mm"],
                                  height_mm=document["page_height_mm"])
    portrait = BytesIO()
    with Image.new("RGB", (60, 80), "#B5CDFF") as image:
        image.save(portrait, format="PNG")
    def resource(layer):
        if layer["type"] == "image":
            return ImageResource(background, sha256(background).hexdigest())
        if layer["type"].endswith("qr"):
            return QrResource("SAMPLE", dummy=True)
        if layer["type"] == "logo" or layer["type"] == "photo" and photo:
            content = portrait.getvalue()
            return ImageResource(content, sha256(content).hexdigest())
    output = BytesIO()
    canvas = Canvas(output, invariant=1, pagesize=(document["page_width_mm"]*mm, document["page_height_mm"]*mm))
    draw_document(canvas, document, {"name": "Alexandra-Marie Fernández", "event": "Community maker programme",
        "eventDate": "18 October 2026", "issueDate": "19 October 2026", "organisation": "Space Works",
        "certificate_id": "SAMPLE-123"}, resource, preview=True)
    canvas.showPage()
    canvas.save()
    assert output.getvalue().startswith(b"%PDF-")
    assert b"%%EOF" in output.getvalue()
    if seed["theme"] == "dark":
        assert all(layer.get("colour_token") != "ink" for layer in document["layers"])


def test_seed_resources_are_fresh_data_and_untrusted_image_ids_refuse(monkeypatch):
    monkeypatch.setattr(seeds, "_catalogue", template_catalogue)
    first = seeds.catalogue(kind="badge", theme="light", stock="cr80-landscape")
    first[0]["resources"][0]["path"] = "https://example.invalid"
    second = seeds.catalogue(kind="badge", theme="light", stock="cr80-landscape")
    assert second[0]["resources"][0]["path"].startswith("artwork/")
    document = deepcopy(second[0]["document"])
    document["layers"][0]["resource_id"] = "11111111-1111-4111-8111-111111111111"
    with pytest.raises(ValidationError):
        validate_design(document, "cr80-landscape")
    with pytest.raises(ValidationError):
        packaged_resource("../../outside.svg")


def test_checksum_change_refuses_before_svg_decode(monkeypatch):
    from apps.events.certificates import seed_artwork
    resource = CERTIFICATE_SEEDS[0]["resources"][0]
    monkeypatch.setattr(seed_artwork.Path, "read_bytes", lambda path: b"<svg/>")
    with pytest.raises(ValidationError, match="checksum"):
        render_packaged(resource["id"], width_mm=297, height_mm=210)

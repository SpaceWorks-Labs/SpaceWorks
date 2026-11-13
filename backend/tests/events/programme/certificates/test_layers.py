from copy import deepcopy
from io import BytesIO
import json
from pathlib import Path

import pytest
from rest_framework.exceptions import ValidationError

from apps.events.certificates.layout import normalize_document
from apps.events.certificates.layer_rendering import QrResource, draw_document
from apps.events.certificates.badge_designs import validate_design

FIXTURES = Path(__file__).parents[1] / "contracts" / "fixtures"


def document():
    return json.loads((FIXTURES / "template-seed-v2.json").read_text())["seed"]["document"]


def test_frozen_artwork_document_validates_without_a_parallel_schema():
    assert normalize_document(document())["layers"][0]["text"] == "{{name}}"
    badge = json.loads((FIXTURES / "template-seed-v2.json").read_text())["badge_seed"]
    assert validate_design(badge["document"], badge["stock"])["version"] == 2


@pytest.mark.parametrize("patch", [
    {"text": "{{email}}"}, {"text": "{{registration.member.email}}"},
    {"font_family": "Comic Sans"}, {"font_size_pt": 5.9}, {"font_weight": True},
    {"x_mm": float("nan")}, {"x_mm": True}, {"width_mm": -1},
    {"rotation": 45, "x_mm": 0, "y_mm": 0}, {"external_url": "https://attacker.test/x"},
    {"italic": True}, {"opacity": 2},
])
def test_untrusted_layers_reject_contact_tags_nonfinite_or_unapproved_styles(patch):
    value = document()
    value["layers"][0].update(patch)
    with pytest.raises(ValidationError):
        normalize_document(value)


def test_order_uuid_count_and_unbounded_accent_limits():
    for alter in (lambda rows: rows.append(deepcopy(rows[0])),
                  lambda rows: rows[0].update(order=19),
                  lambda rows: rows.extend(deepcopy(rows) * 6)):
        value = document()
        alter(value["layers"])
        with pytest.raises(ValidationError):
            normalize_document(value)


def test_badge_stock_exception_does_not_allow_arbitrary_tiny_pages_or_qr():
    value = json.loads((FIXTURES / "template-seed-v2.json").read_text())["badge_seed"]["document"]
    validate_design(value, "cr80-landscape")
    with pytest.raises(ValidationError):
        validate_design(value, "3x4")
    value["layers"][1]["width_mm"] = 12
    with pytest.raises(ValidationError):
        validate_design(value, "cr80-landscape")


def test_render_uses_same_physical_geometry_and_deterministic_branded_fonts():
    from reportlab.pdfgen.canvas import Canvas
    from reportlab.lib.units import mm
    doc = normalize_document(document())
    def render():
        output = BytesIO()
        canvas = Canvas(output, pagesize=(doc["page_width_mm"]*mm, doc["page_height_mm"]*mm), invariant=1)
        draw_document(canvas, doc, {"name": "A long recipient name", "certificate_id": "SAMPLE"},
                      lambda layer: QrResource("SAMPLE", dummy=True) if layer["type"] == "certificate_qr" else None,
                      preview=True)
        canvas.showPage(); canvas.save()
        return output.getvalue()
    first = render()
    assert first.startswith(b"%PDF") and first == render()

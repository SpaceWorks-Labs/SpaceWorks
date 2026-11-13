"""The designer's barcode encoding route and the holder face's per-symbology codes (decision 345(c))."""
import base64

import pytest
from django.urls import reverse

from apps.card_designs import resolution
from apps.card_designs.models import CardDesign
from tests.l3_local.helpers import card_space, client, manager, member

pytestmark = pytest.mark.django_db


def _design(space, actor):
    design, _created = resolution.get_or_create(space, "member_cards", actor=actor)
    return design


def test_the_designer_gets_the_same_encoding_print_uses():
    from apps.card_designs.barcode_symbols import encode
    space = card_space("bc-route")
    sm = manager(space)
    url = reverse("admin-card-design-barcode", args=[_design(space, sm).pk])
    body = client(sm).post(url, {"symbology": "datamatrix", "value": "TNK-0042"}, format="json").json()
    assert body == encode("datamatrix", "TNK-0042")
    # A value the symbology cannot carry previews the sample, like the server's preview render.
    assert client(sm).post(url, {"symbology": "ean13", "value": "TNK-0042"}, format="json").json()["text"] == "5901234123457"
    assert client(sm).post(url, {"symbology": "nope", "value": "x"}, format="json").status_code == 400


def test_members_cannot_use_the_encoding_route():
    space = card_space("bc-rbac")
    design = _design(space, manager(space))
    user, _membership = member(space)
    response = client(user).post(reverse("admin-card-design-barcode", args=[design.pk]),
                                 {"symbology": "aztec", "value": "x"}, format="json")
    assert response.status_code in (403, 404)


def test_the_printed_face_carries_each_symbology_the_design_uses():
    from apps.card_designs.rendering_extras import barcode_svg_uri
    from apps.card_designs.views_holder_face import _barcodes
    doc = {"version": 3, "front": {"layers": [{"kind": "barcode", "source": "number", "symbology": "aztec"}]},
           "back": {"layers": []}, "back_enabled": False}
    out = _barcodes(doc, type("C", (), {"values": {"number": "TNK-0042"}, "desk_qr": "DESKCODE"})(),
                    lambda layer, context: context.values["number"] if layer["source"] == "number" else context.desk_qr,
                    barcode_svg_uri)
    assert set(out) == {"number", "desk", "number:aztec"}
    svg = base64.b64decode(out["number:aztec"].split(",", 1)[1]).decode()
    assert svg.startswith("<svg") and "<rect" in svg
    assert CardDesign.objects.count() == 0

"""The designer's print-ready proof and the per-card print-ready downloads (decision 344(b))."""
import pytest
from django.urls import reverse

from apps.card_designs import resolution
from tests.l3_local.helpers import card_space, client, issue, manager, member

pytestmark = pytest.mark.django_db
PT_PER_MM = 72 / 25.4


def _size(pdf):
    import pypdfium2 as pdfium
    return pdfium.PdfDocument(pdf)[0].get_size()


def test_the_preview_route_returns_a_print_ready_proof_with_bleed_and_marks():
    space = card_space("ps-proof")
    sm = manager(space)
    design, _created = resolution.get_or_create(space, "member_cards", actor=sm)
    response = client(sm).post(reverse("admin-card-design-preview", args=[design.pk]),
                               {"document": design.document, "format": "pdf", "bleed_mm": 3, "crop_marks": True},
                               format="json")
    assert response.status_code == 200 and response["Content-Type"] == "application/pdf"
    width, _height = _size(response.content)
    trim = design.document["front"]["page_width_mm"]
    assert width == pytest.approx((trim + 20) * PT_PER_MM, abs=0.1)


def test_the_preview_route_refuses_a_bleed_over_5_mm():
    space = card_space("ps-bleed")
    sm = manager(space)
    design, _created = resolution.get_or_create(space, "member_cards", actor=sm)
    response = client(sm).post(reverse("admin-card-design-preview", args=[design.pk]),
                               {"document": design.document, "format": "pdf", "bleed_mm": 9}, format="json")
    assert response.status_code == 400


def test_a_member_card_downloads_print_ready_and_plain():
    space = card_space("ps-download")
    sm = manager(space)
    _user, membership = member(space)
    card = issue(space, membership, by=sm)
    url = reverse("admin-member-card-download", args=[card.pk])
    plain = client(sm).get(url, {"format": "pdf"})
    ready = client(sm).get(url, {"format": "pdf", "bleed_mm": "3", "crop_marks": "true"})
    assert plain.status_code == ready.status_code == 200
    assert _size(ready.content)[0] == pytest.approx(_size(plain.content)[0] + 20 * PT_PER_MM, abs=0.1)
    assert "-print.pdf" in ready["Content-Disposition"]
    assert client(sm).get(url, {"bleed_mm": "nope"}).status_code == 400

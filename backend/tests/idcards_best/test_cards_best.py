"""LOCAL tests for the r2-idcards-best card engine additions (never committed)."""
import pytest
from rest_framework.exceptions import ValidationError

from apps.audit.models import AuditLog
from apps.card_designs import designs, resolution
from apps.card_designs.default_templates import LABELS, THEMES, build
from apps.card_designs.layout import normalize_document
from apps.card_designs.layout_layers import normalize_layer
from tests.l3_local.helpers import card_space, client, issue, manager, member

pytestmark = pytest.mark.django_db
DOMAINS = ("member_cards", "id_programme", "event_card", "event_ticket")


@pytest.mark.parametrize("theme", THEMES)
@pytest.mark.parametrize("domain", DOMAINS)
def test_every_template_both_themes_is_two_sided_and_passes_contrast(domain, theme):
    for key in LABELS:
        document = normalize_document(build(key, domain, theme))
        assert document["back_enabled"] is True
        assert document["back"]["layers"], key
        assert document["front"]["page_width_mm"] in (85.6, 53.98)


def test_dark_theme_recolours_only_text_on_the_card_background():
    light, dark = build("classic", "member_cards"), build("classic", "member_cards", "dark")
    assert dark["front"]["background"]["colour"] == "#142C2A"
    by_name = {layer["name"]: layer for layer in dark["front"]["layers"]}
    assert by_name["Name"]["colour"] == "#FFF4E8"
    # Text on the teal band keeps its cream.
    assert by_name["Space name"]["colour"] == {l["name"]: l for l in light["front"]["layers"]}["Space name"]["colour"]


def _layer(**extra):
    base = {"id": "6a2f1c2e-1b2c-4d5e-8f90-123456789abc", "kind": "barcode", "name": "", "x_mm": 3, "y_mm": 30,
            "w_mm": 40, "h_mm": 9, "rotation": 0, "opacity": 100}
    return {**base, **extra}


def test_barcode_layer_bounds():
    row = normalize_layer(_layer(), 85.6, 53.98, "cr80-landscape")
    assert row["source"] == "number" and row["show_text"] is True and row["group"] is None
    with pytest.raises(ValidationError):
        normalize_layer(_layer(source="desk"), 85.6, 53.98, "cr80-landscape")  # 40 mm < 75 mm
    normalize_layer(_layer(source="desk", w_mm=78), 85.6, 53.98, "cr80-landscape")
    with pytest.raises(ValidationError):
        normalize_layer(_layer(rotation=10), 85.6, 53.98, "cr80-landscape")
    with pytest.raises(ValidationError):
        normalize_layer(_layer(h_mm=4), 85.6, 53.98, "cr80-landscape")
    with pytest.raises(ValidationError):
        normalize_layer(_layer(source="token"), 85.6, 53.98, "cr80-landscape")


def test_photo_filter_and_group_normalise():
    photo = {**_layer(kind="photo", w_mm=18, h_mm=22), "filter": "duotone", "duotone_dark": "#142c2a",
             "group": "7b2f1c2e-1b2c-4d5e-8f90-123456789abc"}
    row = normalize_layer(photo, 85.6, 53.98, "cr80-landscape")
    assert row["filter"] == "duotone" and row["duotone_dark"] == "#142C2A" and row["group"]
    with pytest.raises(ValidationError):
        normalize_layer({**photo, "filter": "sepia"}, 85.6, 53.98, "cr80-landscape")


def test_barcode_and_filters_render_to_pdf_and_png():
    from io import BytesIO
    from PIL import Image
    from apps.card_designs.rendering import RenderContext, render_png
    from apps.card_designs.rendering_extras import barcode_svg_uri, filtered_photo
    document = build("classic", "member_cards")
    document["front"]["layers"].append(_layer(y_mm=41, w_mm=50, h_mm=9))
    document = normalize_document(document)
    buffer = BytesIO()
    Image.new("RGB", (60, 80), "#3366CC").save(buffer, "JPEG")
    photo = buffer.getvalue()
    for kind in ("grey", "duotone"):
        out = filtered_photo(photo, {"filter": kind, "duotone_dark": "#142C2A", "duotone_light": "#DFFF8F"})
        assert out != photo and Image.open(BytesIO(out)).size == (60, 80)
    png = render_png(document, RenderContext(values={"name": "Priya", "number": "TNK-0042"}, desk_qr="a" * 32,
                                              photo=photo))
    assert Image.open(BytesIO(png)).size == (1011, 638)
    assert barcode_svg_uri("TNK-0042").startswith("data:image/svg+xml;base64,")
    assert barcode_svg_uri("") is None


def test_one_line_fit_prefers_a_single_shrunk_line():
    from apps.card_designs.rendering_text import fit
    layer = {"font_family": "Gilroy", "font_weight": 700, "font_size_pt": 11, "line_height": 1.15,
             "tracking_pt": 0, "shrink_to_fit": True}
    size, lines = fit("Alexandra Montgomery", layer, 100, 14)  # one line tall
    assert len(lines) == 1 and 11 * 0.6 <= size < 11
    size, lines = fit("Alexandra Montgomery", layer, 100, 30)  # two lines fit at full size
    assert size == 11 and len(lines) == 2


def test_history_lists_and_restores_as_a_new_revision():
    space = card_space("ib-hist")
    sm = manager(space)
    design, _ = resolution.get_or_create(space, "member_cards", actor=sm)
    designs.save(sm, design, build("bold", "member_cards"), expected_revision=1)
    api = client(sm)
    page = api.get(f"/api/v1/admin/card-designs/{design.pk}/revisions").json()
    assert page["count"] == 2 and page["results"][0]["is_current"]
    detail = api.get(f"/api/v1/admin/card-designs/{design.pk}/revisions/1")
    assert detail.status_code == 200 and detail.json()["document"]["front"]["layers"]
    conflict = api.post(f"/api/v1/admin/card-designs/{design.pk}/revisions/1/restore", {"revision": 1}, format="json")
    assert conflict.status_code == 409
    restored = api.post(f"/api/v1/admin/card-designs/{design.pk}/revisions/1/restore", {"revision": 2}, format="json")
    assert restored.status_code == 200, restored.content
    assert restored.json()["revision"] == 3
    assert AuditLog.objects.filter(action="card_design.restored").exists()
    assert api.get(f"/api/v1/admin/card-designs/{design.pk}/revisions/99").status_code == 404


def test_templates_list_has_both_themes_and_reset_takes_a_theme():
    space = card_space("ib-tpl")
    sm = manager(space)
    design, _ = resolution.get_or_create(space, "member_cards", actor=sm)
    api = client(sm)
    rows = api.get(f"/api/v1/admin/card-designs/{design.pk}/templates").json()
    assert len(rows) == 12 and {row["theme"] for row in rows} == {"light", "dark"}
    reset = api.post(f"/api/v1/admin/card-designs/{design.pk}/reset", {"template": "minimal", "theme": "dark"},
                     format="json")
    assert reset.status_code == 200 and reset.json()["document"]["front"]["background"]["colour"] == "#142C2A"


def test_preview_as_a_real_holder_and_outsiders_cannot():
    space = card_space("ib-prev")
    other = card_space("ib-prev-other")
    sm = manager(space)
    _user, membership = member(space)
    card = issue(space, membership, sm)
    design, _ = resolution.get_or_create(space, "member_cards", actor=sm)
    api = client(sm)
    holders = api.get(f"/api/v1/admin/card-designs/{design.pk}/holders").json()
    assert [row["id"] for row in holders] == [card.pk]
    body = {"document": design.document, "format": "png", "holder_id": card.pk}
    preview = api.post(f"/api/v1/admin/card-designs/{design.pk}/preview", body, format="json")
    assert preview.status_code == 200 and preview["Content-Type"] == "image/png"
    assert AuditLog.objects.filter(action="card_design.previewed_as_holder").exists()
    other_member = member(other, "x")[1]
    stranger = issue(other, other_member, manager(other))
    missing = api.post(f"/api/v1/admin/card-designs/{design.pk}/preview", {**body, "holder_id": stranger.pk},
                       format="json")
    assert missing.status_code == 404


def test_calibration_sheet_for_every_paper():
    space = card_space("ib-cal")
    sm = manager(space)
    design, _ = resolution.get_or_create(space, "member_cards", actor=sm)
    api = client(sm)
    for paper in ("a4", "letter", "card"):
        response = api.get(f"/api/v1/admin/card-designs/{design.pk}/calibration?paper={paper}")
        assert response.status_code == 200 and response.content.startswith(b"%PDF")
    assert api.get(f"/api/v1/admin/card-designs/{design.pk}/calibration?paper=a3").status_code == 400


def test_calibration_handles_a_large_stock():
    from apps.card_designs import calibration
    pdf = calibration.render(normalize_document(build("classic", "member_cards") | {"stock": "a6-portrait"}
                                                | _scaled_a6()), "a4")
    assert pdf.startswith(b"%PDF")


def _scaled_a6():
    side = {"page_width_mm": 105.0, "page_height_mm": 148.0, "background": {"kind": "colour", "colour": "#FFFFFF"},
            "layers": []}
    return {"front": side, "back": side, "back_enabled": False}


def test_member_card_sheet_preview_counts_and_audits():
    space = card_space("ib-sheet")
    sm = manager(space)
    for index in range(3):
        issue(space, member(space, f"m{index}")[1], sm)
    response = client(sm).post(f"/api/v1/admin/makerspaces/{space.pk}/member-card-jobs/preview",
                               {"paper": "a4", "order": "duplex"}, format="json")
    assert response.status_code == 200, response.content
    body = response.json()
    assert body["total"] == 3 and body["per_page"] == 10 and body["sheets"] == 1
    assert body["front"].startswith("data:image/png") and body["back"].startswith("data:image/png")
    assert AuditLog.objects.filter(action="card_job.previewed").exists()
    empty = client(sm).post(f"/api/v1/admin/makerspaces/{space.pk}/member-card-jobs/preview",
                            {"card_ids": [999999]}, format="json").json()
    assert empty["total"] == 0 and empty["front"] is None


def test_face_carries_barcodes():
    from apps.card_designs.views_holder_face import face
    space = card_space("ib-face")
    sm = manager(space)
    _user, membership = member(space)
    card = issue(space, membership, sm)
    data = face("member_card", card)
    assert set(data["barcodes"]) == {"number", "desk"}
    assert data["barcodes"]["desk"].startswith("data:image/svg+xml")


def test_save_keeps_a_v2_document_with_new_layer_kinds():
    space = card_space("ib-save")
    sm = manager(space)
    design, _ = resolution.get_or_create(space, "member_cards", actor=sm)
    document = build("classic", "member_cards")
    document["front"]["layers"].append(_layer(y_mm=41, w_mm=50, h_mm=9))
    saved = designs.save(sm, design, document, expected_revision=1)
    assert any(layer["kind"] == "barcode" for layer in saved.document["front"]["layers"])


def test_event_card_print_filters_by_role_and_check_in_and_previews():
    from apps.events import id_cards
    from apps.events.id_cards_preview import event_card_ids
    from apps.events.models import EventIdCard, EventRegistration
    from tests.l3_local.test_event_cards import _event, _registration
    space, event = _event("ib-evf")
    sm = manager(space)
    _u1, first = _registration(space, event, "a1")
    _u2, second = _registration(space, event, "a2")
    design, _ = resolution.get_or_create(space, "event_card", actor=sm, event=event)
    designs.publish(sm, design)
    id_cards.reconcile_event(event.pk)
    EventIdCard.objects.filter(registration=second).update(role="mentor")
    EventRegistration.objects.filter(pk=first.pk).update(status=EventRegistration.Status.ATTENDED)
    card_one = EventIdCard.objects.get(registration=first).pk
    assert event_card_ids(event, {"roles": ["mentor"]}) == [EventIdCard.objects.get(registration=second).pk]
    assert event_card_ids(event, {"checked_in": True}) == [card_one]
    assert card_one not in event_card_ids(event, {"checked_in": False})
    response = client(sm).post(f"/api/v1/admin/events/{event.pk}/card-jobs/preview", {"roles": ["attendee"]},
                               format="json")
    assert response.status_code == 200, response.content
    assert response.json()["total"] == 1


def test_programme_sheet_preview_route_needs_the_capability():
    space = card_space("ib-prog")
    sm = manager(space)
    response = client(sm).post("/api/v1/admin/id-programmes/999999/card-jobs/preview", {}, format="json")
    assert response.status_code == 404

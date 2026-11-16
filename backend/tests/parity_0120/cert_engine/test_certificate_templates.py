"""The three built-in certificate templates: valid, AA-readable, inside the print margin, gallery rows and the read route."""
import pytest
from django.urls import reverse

from apps.card_designs import templates
from apps.card_designs.data_fields import CERTIFICATE_SAMPLE
from apps.card_designs.default_templates import CERTIFICATE_LOOKS, THEMES, build, build_certificate
from apps.card_designs.layout import normalize_document
from apps.card_designs.rendering import RenderContext, render_pdf
from tests.l3_local.helpers import card_space, client, manager

from .helpers import signatory, uid

KEYS = ("cert_laurel", "cert_ribbon", "cert_spotlight")
MARGIN_MM = 10.0


def test_there_are_three_certificate_looks():
    assert tuple(CERTIFICATE_LOOKS) == KEYS and set(CERTIFICATE_LOOKS.values()) == {"Laurel", "Ribbon", "Spotlight"}


@pytest.mark.parametrize("key", KEYS)
@pytest.mark.parametrize("theme", THEMES)
def test_every_look_passes_the_aa_text_check_in_both_themes(key, theme):
    document = normalize_document(build_certificate(key, theme), check_contrast=True)  # raises below 4.5:1
    assert document["kind"] == "certificate" and document["stock"] == "a4-landscape" and not document["back_enabled"]
    assert (document["front"]["page_width_mm"], document["front"]["page_height_mm"]) == (297.0, 210.0)


@pytest.mark.parametrize("key", KEYS)
@pytest.mark.parametrize("theme", THEMES)
def test_every_look_has_signatories_serial_and_verification_and_keeps_the_print_margin(key, theme):
    document = normalize_document(build_certificate(key, theme))
    layers = document["front"]["layers"]
    kinds = {row["kind"] for row in layers}
    assert {"verify_qr", "certificate_id"} <= kinds and kinds & {"signature", "signature_row"}
    for row in layers:
        if row["kind"] in ("seal", "band", "shape", "logo") or row.get("decorative"):
            continue
        assert row["x_mm"] >= MARGIN_MM - 0.01 and row["y_mm"] >= MARGIN_MM - 0.01, row["name"]
        assert row["x_mm"] + row["w_mm"] <= 297 - MARGIN_MM + 0.01 and row["y_mm"] + row["h_mm"] <= 210 - MARGIN_MM + 0.01, row["name"]
    assert document["guides"]["margin_mm"] == 10.0


@pytest.mark.parametrize("key", KEYS)
@pytest.mark.parametrize("theme", THEMES)
def test_every_look_renders_with_sample_values_and_with_a_winner_and_a_long_name(key, theme):
    document = normalize_document(build_certificate(key, theme))
    people = {slot: signatory(f"Signatory {slot}", "Director", image=False) for slot in (1, 2, 3)}
    for values in (CERTIFICATE_SAMPLE, {**CERTIFICATE_SAMPLE, "recipient": "Alexandra Montgomery-Fitzgerald",
                                        "first_name": "Alexandra", "last_name": "Montgomery-Fitzgerald",
                                        "achievement": "", "place": ""}):
        pdf = render_pdf(document, RenderContext(values=values, signatories=people, preview=True))
        assert pdf.startswith(b"%PDF")


def test_the_spotlight_look_prints_three_signatories_in_one_row():
    row = next(layer for layer in normalize_document(build_certificate("cert_spotlight", "light"))["front"]["layers"]
               if layer["kind"] == "signature_row")
    assert row["slots"] == [1, 2, 3]


def test_an_unknown_look_or_theme_is_refused():
    from rest_framework.exceptions import ValidationError
    for key, theme in (("cert_nope", "light"), ("cert_laurel", "sepia")):
        with pytest.raises(ValidationError):
            build_certificate(key, theme)


def test_the_gallery_lists_certificate_looks_with_kind_certificate():
    rows = templates.builtin_rows("certificate")
    assert len(rows) == 6 and {row["kind"] for row in rows} == {"certificate"}
    assert {row["id"] for row in rows} == {f"builtin:{key}:{theme}" for key in KEYS for theme in THEMES}
    assert all(row["stock"] == "a4-landscape" and row["orientation"] == "landscape" for row in rows)
    assert all(row["kind"] == "card" for row in templates.builtin_rows("card"))
    assert {row["kind"] for row in templates.builtin_rows()} == {"card", "certificate"}


@pytest.mark.django_db
def test_the_builtin_read_route_returns_a_look_with_its_document():
    space = card_space("cert-tpl-route")
    api = client(manager(space))
    url = reverse("admin-card-template-builtin", kwargs={"makerspace_id": space.pk, "key": "cert_laurel", "theme": "dark"})
    data = api.get(url).json()
    assert data["id"] == "builtin:cert_laurel:dark" and data["kind"] == "certificate" and data["document"]["kind"] == "certificate"
    card = api.get(reverse("admin-card-template-builtin", kwargs={"makerspace_id": space.pk, "key": "studio_lanyard", "theme": "light"}))
    assert card.json()["document"]["stock"] == "cr80-portrait"
    for key, theme in (("cert_nope", "light"), ("cert_laurel", "sepia")):
        assert api.get(reverse("admin-card-template-builtin", kwargs={"makerspace_id": space.pk, "key": key, "theme": theme})).status_code == 404
    listing = api.get(reverse("admin-card-templates", kwargs={"makerspace_id": space.pk}), {"kind": "certificate"}).json()
    assert {row["kind"] for row in listing} == {"certificate"} and len(listing) == 6


@pytest.mark.django_db
def test_a_certificate_document_is_saved_as_a_space_template_without_images():
    space = card_space("cert-tpl-save")
    api = client(manager(space))
    url = reverse("admin-card-templates", kwargs={"makerspace_id": space.pk})
    document = build_certificate("cert_ribbon", "light")
    made = api.post(url, {"document": document, "name": "My certificate"}, format="json")
    assert made.status_code == 201, made.content
    assert made.json()["kind"] == "certificate" and made.json()["stock"] == "a4-landscape"
    assert [row["name"] for row in api.get(url, {"kind": "certificate", "source": "space"}).json()] == ["My certificate"]
    assert api.post(url, {"document": document, "design_id": 1, "name": "Both"}, format="json").status_code == 400
    assert api.post(url, {"name": "Neither"}, format="json").status_code == 400
    card = build("classic", "member_cards", "light")
    assert api.post(url, {"document": card, "name": "A card"}, format="json").status_code == 400
    pictured = build_certificate("cert_laurel", "light")
    pictured["front"]["background"] = {"kind": "image", "asset_id": uid(), "fallback": "#FFFFFF"}
    assert api.post(url, {"document": pictured, "name": "Pictured"}, format="json").status_code == 400

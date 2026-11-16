"""The three Card Studio built-in looks: valid v3 documents in both themes with contrast, for every card domain."""
import pytest

from apps.card_designs.default_templates import LABELS, TEMPLATES, THEMES, build
from apps.card_designs.layout import normalize_document
from apps.card_designs.rendering import RenderContext, render_pdf
from apps.card_designs.studio_samples import silhouette_png

STUDIO = ("studio_lanyard", "studio_spotlight", "studio_arch")


def test_the_studio_looks_are_registered_and_portrait():
    assert all(key in TEMPLATES and key in LABELS for key in STUDIO)
    for key in STUDIO:
        assert build(key, "member_cards")["stock"] == "cr80-portrait"


@pytest.mark.parametrize("key", STUDIO)
@pytest.mark.parametrize("theme", THEMES)
@pytest.mark.parametrize("domain", ["member_cards", "id_programme", "event_card", "staff_cards"])
def test_every_studio_look_validates_with_contrast(key, theme, domain):
    document = normalize_document(build(key, domain, theme), check_contrast=True)
    assert document["back_enabled"] and document["version"] == 3


def test_the_lanyard_look_has_the_reference_ingredients():
    document = normalize_document(build("studio_lanyard", "member_cards", "dark"), check_contrast=True)
    front = document["front"]
    kinds = {layer["name"]: layer for layer in front["layers"]}
    assert front["background"]["kind"] == "gradient" and front["overlay"]
    assert kinds["Background lettering"]["decorative"] and kinds["Background lettering"]["font_family"] == "Bebas Neue"
    photo = kinds["Photo"]
    assert photo["variant"] == "cutout" and photo["outline"]["colour"] == "#FFFFFF" and photo["shadow"]
    assert [span["font_weight"] for span in kinds["Name"]["spans"]] == [300, 800]
    assert kinds["Role"]["highlight"]["colour"] == "#DFFF8F" and kinds["Department"]["font_family"] == "Pacifico"
    assert {"Space logo", "Organisation logo"} <= set(kinds) and document["guides"]["punch_slot"]["shape"] == "slot"


@pytest.mark.parametrize("key", STUDIO)
def test_the_studio_looks_render_with_and_without_a_cutout(key):
    document = normalize_document(build(key, "member_cards", "light"), check_contrast=False)
    values = {"name": "Fathima Shenza", "space": "Tinkerspace", "role": "Member", "team": "Electronics"}
    for context in (RenderContext(values=values, photo_cutout=silhouette_png(), use_cutout=True), RenderContext(values=values)):
        assert render_pdf(document, context).startswith(b"%PDF")

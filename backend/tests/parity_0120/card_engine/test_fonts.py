"""Card Studio fonts: only the free Gilroy weights and open faces ship; each has its licence; the renderer can embed or
outline-draw every one."""
from pathlib import Path

import pytest
from rest_framework.exceptions import ValidationError

from apps.card_designs import fonts
from apps.card_designs.layout import normalize_document

from .conftest import document, layer

REPO = Path(__file__).resolve().parents[4]
STUDIO = {"Gilroy Light": (300,), "Gilroy ExtraBold": (800,), "Outfit": (300, 400, 500, 600, 700, 800),
          "Unbounded": (400, 500, 600, 700, 800), "Bebas Neue": (400,), "Pacifico": (400,), "DM Serif Display": (400,)}


def test_the_studio_allow_list_is_exactly_the_agreed_families():
    assert set(fonts.STUDIO_FONTS) == set(STUDIO)
    for family, weights in STUDIO.items():
        # the library is the full catalogue (C-21): a studio family may offer more weights than we vendor
        assert set(weights) <= set(fonts.family_weights(family))


@pytest.mark.parametrize("family", sorted(STUDIO))
def test_every_studio_face_is_vendored_with_its_licence_in_backend_and_frontend(family):
    licence = fonts.STUDIO_FONTS[family][1]
    assert (fonts.STUDIO_DIR / licence).is_file()
    for weight in STUDIO[family]:
        assert fonts.bundled_path(family, weight).is_file()
    if family.startswith("Gilroy"):
        assert (REPO / "frontend" / "public" / "fonts" / f"{family.replace(' ', '-').replace('Gilroy-', 'Gilroy-')}.woff2").is_file()
    elif family in ("Bebas Neue", "Pacifico", "DM Serif Display"):
        assert (REPO / "frontend" / "public" / "fonts" / "LICENSES" / licence).is_file()
        assert (REPO / "frontend" / "public" / "fonts" / f"{family.replace(' ', '')}-400.woff2").is_file()


def test_no_paid_gilroy_weight_is_selectable_and_the_legacy_token_stays_outfit():
    assert fonts.family_weights("Gilroy Bold") == () and fonts.family_weights("Gilroy Regular") == ()
    assert fonts.canonical("Gilroy") == "Outfit"
    with pytest.raises(ValidationError):
        normalize_document(document([layer("text", 1, 1, 40, 8, text="x", font_family="Gilroy Light", font_weight=700)]),
                           check_contrast=False)


def test_gilroy_is_outline_drawn_and_the_others_are_embedded():
    assert fonts.is_outline("Gilroy Light", 300) and fonts.is_outline("Gilroy ExtraBold", 800)
    assert not fonts.is_outline("Outfit", 800) and not fonts.is_outline("Pacifico", 400)


def test_outline_faces_measure_and_draw_without_embedding():
    from reportlab.pdfgen.canvas import Canvas
    from io import BytesIO
    from apps.card_designs import rendering_outline as outline
    name = outline.pseudo_name("Gilroy ExtraBold", 800)
    assert outline.string_width("SHENZA", name, 20) > outline.string_width("SHE", name, 20) > 0
    buffer = BytesIO()
    canvas = Canvas(buffer)
    assert outline.draw_string(canvas, "SHENZA", name, 20, 10, 10) > 10
    canvas.showPage()
    canvas.save()
    assert b"Gilroy" not in buffer.getvalue()  # drawn as paths: no font file is embedded


def test_the_picker_lists_the_studio_faces_first():
    total, rows = fonts.search("", limit=len(STUDIO))
    assert [row["family"] for row in rows[:len(STUDIO)]] == list(fonts.STUDIO_FONTS)
    assert total > len(STUDIO)


def test_the_renderer_font_dir_holds_only_free_faces_each_with_a_licence():
    files = sorted(path.name for path in fonts.STUDIO_DIR.iterdir() if path.suffix in (".ttf", ".otf"))
    assert files == sorted([
        "BebasNeue-400.ttf", "DMSerifDisplay-400.ttf", "Gilroy-ExtraBold.otf", "Gilroy-Light.otf", "Outfit-300.ttf",
        "Outfit-800.ttf", "Pacifico-400.ttf", "Unbounded-800.ttf"])
    assert not [name for name in files if name.startswith("Gilroy") and not name.startswith(("Gilroy-Light", "Gilroy-ExtraBold"))]
    for licence in {entry[1] for entry in fonts.STUDIO_FONTS.values()}:
        assert (fonts.STUDIO_DIR / licence).is_file()

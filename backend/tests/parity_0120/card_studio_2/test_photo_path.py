"""The ID-card photo path (decision 344(a)): the cut-out prints over any background with the frame's crop, and falls
back to the original whenever it is missing, not chosen (auto) or switched off; quota, staleness and storage fixes."""
from io import BytesIO

import pytest
from PIL import Image

from apps.card_designs.layout import normalize_document
from apps.card_designs.rendering import RenderContext, render_png
from apps.card_designs.rendering_photo import photo_source

from .conftest import document, layer, png, silhouette, uid

MM = 300 / 25.4
RED, BLUE, GREEN = (180, 40, 40), (20, 20, 200), (0, 160, 60)


def _pixel(data, x_mm, y_mm):
    return Image.open(BytesIO(data)).convert("RGB").getpixel((round(x_mm * MM), round(y_mm * MM)))


def _near(actual, expected, tolerance=30):
    return all(abs(a - b) <= tolerance for a, b in zip(actual, expected))


def _card(variant, background, **photo):
    return normalize_document(document([layer("photo", 10, 10, 24, 32, shape="square", variant=variant, **photo)],
                                       background=background), check_contrast=False)


ASSET = uid()
BACKGROUNDS = {"colour": ({"kind": "colour", "colour": "#00A03C"}, {}),
               "image": ({"kind": "image", "asset_id": ASSET, "fit": "cover", "dim_pct": 0}, {ASSET: png((40, 40), (0, 160, 60, 255))}),
               "gradient": ({"kind": "gradient", "type": "linear", "angle_deg": 0,
                             "stops": [{"colour": "#00A03C", "at": 0}, {"colour": "#00A03C", "at": 100}]}, {})}


@pytest.mark.parametrize("name", BACKGROUNDS)
def test_the_cutout_sits_over_every_kind_of_background(name):
    background, assets = BACKGROUNDS[name]
    context = RenderContext(photo=png((60, 80), (*RED, 255)), photo_cutout=silhouette(), use_cutout=False, assets=assets)
    out = render_png(_card("cutout", background), context)
    assert _near(_pixel(out, 22, 26), BLUE)  # the person
    assert _near(_pixel(out, 11, 11), GREEN)  # the erased corner shows the background, not the old photo


@pytest.mark.parametrize("variant,cutout,chosen,expected", [
    ("original", True, True, RED), ("cutout", True, False, BLUE), ("cutout", False, True, RED),
    ("auto", True, False, RED), ("auto", True, True, BLUE), ("auto", False, True, RED)])
def test_the_variant_picks_the_cutout_or_falls_back_to_the_original(variant, cutout, chosen, expected):
    context = RenderContext(photo=png((60, 80), (*RED, 255)), photo_cutout=silhouette() if cutout else None,
                            use_cutout=chosen)
    out = render_png(_card(variant, BACKGROUNDS["colour"][0]), context)
    assert _near(_pixel(out, 22, 26), expected)


def test_the_cutout_follows_the_frames_zoom_and_focal_point():
    context = RenderContext(photo=None, photo_cutout=silhouette(), use_cutout=True)
    plain = render_png(_card("cutout", BACKGROUNDS["colour"][0]), context)
    zoomed = render_png(_card("cutout", BACKGROUNDS["colour"][0], zoom=2, focal_x_pct=50, focal_y_pct=50), context)
    # 2x around the centre: the transparent border leaves the frame, so a point that was background is now the person.
    assert _near(_pixel(plain, 13, 14), GREEN) and _near(_pixel(zoomed, 13, 14), BLUE)


def test_photo_source_matrix_matches_the_spec():
    class Ctx:
        photo, photo_cutout, use_cutout = b"o", b"c", False
    assert photo_source({"variant": "cutout"}, Ctx) == (b"c", True)
    assert photo_source({"variant": "auto"}, Ctx) == (b"o", False)
    assert photo_source({}, Ctx) == (b"o", False)

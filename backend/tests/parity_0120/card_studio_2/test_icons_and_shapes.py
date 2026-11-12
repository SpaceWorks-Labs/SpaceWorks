"""Icons and polygon shapes (decision 344(b)): validated against a closed library, drawn by the shared renderer."""
from io import BytesIO

import pytest
from PIL import Image
from rest_framework.exceptions import ValidationError

from apps.card_designs import studio_geometry, studio_icons
from apps.card_designs.layout import normalize_document
from apps.card_designs.layout_layers import normalize_layer
from apps.card_designs.rendering import RenderContext, render_pdf, render_png

from .conftest import document, layer

MM = 300 / 25.4


def _norm(value, kind="card"):
    return normalize_layer(value, 54, 85.6, "cr80-portrait", kind)


def _pixel(data, x_mm, y_mm):
    return Image.open(BytesIO(data)).convert("RGB").getpixel((round(x_mm * MM), round(y_mm * MM)))


def test_every_vendored_icon_parses_and_has_a_label():
    for key, icon in studio_icons.catalogue().items():
        assert icon["label"] and studio_icons.commands(key), key


def test_an_icon_layer_keeps_only_its_key_colour_and_mirror():
    row = _norm(layer("icon", 5, 5, 12, 12, icon="pin", colour="#006e63", flip_x=True))
    assert (row["icon"], row["colour"], row["flip_x"]) == ("pin", "#006E63", True)


@pytest.mark.parametrize("bad", [{"icon": "rocket"}, {"icon": "pin", "colour": "teal"},
                                 {"icon": "pin", "paths": ["M0 0 Z"]}, {"icon": "pin", "url": "https://x.test/a.svg"}])
def test_an_icon_outside_the_library_or_with_extra_keys_is_refused(bad):
    with pytest.raises(ValidationError):
        _norm(layer("icon", 5, 5, 12, 12, **bad))


def test_certificates_may_place_icons():
    assert _norm(layer("icon", 5, 5, 12, 12, icon="award"), "certificate")["icon"] == "award"


@pytest.mark.parametrize("shape", studio_geometry.POLYGON_SHAPES)
def test_polygon_shapes_validate_and_render(shape):
    doc = normalize_document(document([layer("shape", 10, 10, 30, 30, shape=shape, fill="#FF0000",
                                             shadow={"dx_mm": 1, "dy_mm": 1, "blur_mm": 1, "colour": "#000000",
                                                     "opacity_pct": 50})]), check_contrast=False)
    out = render_png(doc, RenderContext())
    assert _pixel(out, 25, 26) == pytest.approx((255, 0, 0), abs=20)  # the centre of every polygon is filled
    assert _pixel(out, 10.4, 10.4) == pytest.approx((255, 255, 255), abs=20)  # the box corner is outside it


def test_polygon_points_match_the_spec():
    assert studio_geometry.polygon_points("triangle", 20, 10) == [(10.0, 0.0), (20.0, 10.0), (0.0, 10.0)]
    star = studio_geometry.polygon_points("star", 10, 10)
    assert len(star) == 10 and star[0] == (5.0, 0.0)


def test_an_icon_prints_in_its_colour_and_mono_prints_black_or_white():
    doc = normalize_document(document([layer("icon", 10, 10, 30, 30, icon="plus", colour="#0000FF")]), check_contrast=False)
    assert _pixel(render_png(doc, RenderContext()), 25, 25) == pytest.approx((0, 0, 255), abs=20)
    mono = normalize_document(document([layer("icon", 10, 10, 30, 30, icon="plus", colour="#0000FF")], mono=True),
                              check_contrast=False)
    assert _pixel(render_png(mono, RenderContext()), 25, 25) == pytest.approx((0, 0, 0), abs=20)


def test_an_icon_with_holes_leaves_them_open():
    doc = normalize_document(document([layer("icon", 10, 10, 30, 30, icon="info", colour="#000000")]), check_contrast=False)
    out = render_png(doc, RenderContext())
    # The stem of the "i" is a hole in the filled circle: the background shows through it.
    assert _pixel(out, 25, 10 + 30 * 14 / 24) == pytest.approx((255, 255, 255), abs=30)
    assert _pixel(out, 25 - 30 * 7 / 24, 25) == pytest.approx((0, 0, 0), abs=30)


def test_documents_with_icons_render_to_pdf():
    doc = normalize_document(document([layer("icon", 5, 5, 10, 10, icon=key) for key in ("star", "gear", "wifi")]),
                             check_contrast=False)
    assert render_pdf(doc, RenderContext()).startswith(b"%PDF")

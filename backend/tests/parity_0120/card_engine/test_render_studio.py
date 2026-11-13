"""Card Studio rendering parity on the server: every new property draws, and the pure plan matches what is painted."""
from io import BytesIO

import pytest
from PIL import Image

from apps.card_designs import rendering_rich, studio_geometry
from apps.card_designs.layout import normalize_document
from apps.card_designs.rendering import RenderContext, render_pdf, render_png

from .conftest import document, layer, png, silhouette, uid

MM = 300 / 25.4  # pixels per mm at the PNG's 300 dpi


def render(layers, context=None, *, background=None, side="front", **top):
    doc = normalize_document(document(layers, background=background, **top), check_contrast=False)
    return render_png(doc, context or RenderContext(values={"name": "Fathima Shenza"}), side=side)


def pixel(data, x_mm, y_mm):
    image = Image.open(BytesIO(data)).convert("RGB")
    return image.getpixel((round(x_mm * MM), round(y_mm * MM)))


def close(first, second, tolerance=14):
    return all(abs(a - b) <= tolerance for a, b in zip(first, second))


def test_a_v3_document_renders_to_a_pdf_with_one_page_per_side():
    doc = normalize_document(document([layer("shape", 5, 5, 20, 20, shape="circle", fill="#006E63")], back_enabled=True),
                             check_contrast=False)
    pdf = render_pdf(doc, RenderContext())
    assert pdf.startswith(b"%PDF") and pdf.count(b"/Type /Page\n") + pdf.count(b"/Type /Page ") >= 2


def test_gradient_background_and_overlay_paint_the_expected_colours():
    out = render([], background={"kind": "gradient", "type": "linear", "angle_deg": 180,
                                 "stops": [{"colour": "#FF0000", "at": 0}, {"colour": "#0000FF", "at": 100}]})
    assert close(pixel(out, 27, 2), (255, 0, 0), 25) and close(pixel(out, 27, 83), (0, 0, 255), 25)
    doc = document([])
    doc["front"]["overlay"] = {"type": "linear", "angle_deg": 180, "stops": [
        {"colour": "#000000", "at": 0, "alpha_pct": 0}, {"colour": "#000000", "at": 100, "alpha_pct": 100}]}
    data = render_png(normalize_document(doc, check_contrast=False), RenderContext())
    assert close(pixel(data, 27, 1), (255, 255, 255), 20) and close(pixel(data, 27, 84), (0, 0, 0), 25)


def test_radial_gradient_honours_its_centre():
    spec = {"kind": "gradient", "type": "radial", "angle_deg": 0, "cx_pct": 20, "cy_pct": 20, "radius_pct": 40,
            "stops": [{"colour": "#FF0000", "at": 0}, {"colour": "#FFFFFF", "at": 100}]}
    out = render([], background=spec)
    assert close(pixel(out, 10.8, 17.1), (255, 0, 0), 40) and close(pixel(out, 50, 80), (255, 255, 255), 10)


@pytest.mark.parametrize("shape,inside,outside", [("circle", (27, 40), (21, 36)), ("arch", (27, 50), (22, 24)),
                                                  ("rounded", (27, 40), (21, 31))])
def test_shape_kinds_fill_their_outline_only(shape, inside, outside):
    box = (14, 30, 26, 24) if shape != "arch" else (14, 20, 26, 40)
    out = render([layer("shape", *box, shape=shape, fill="#006E63", radius_mm=6)])
    assert close(pixel(out, *inside), (0, 110, 99))
    if shape in ("circle", "arch"):
        assert close(pixel(out, box[0] + 0.5, box[1] + 0.5), (255, 255, 255), 10)  # the corner stays background


def test_a_shape_honours_its_opacity_in_print():
    out = render([layer("shape", 10, 10, 30, 30, shape="rect", fill="#000000", opacity=50)])
    assert 100 < pixel(out, 25, 25)[0] < 160


def test_gradient_fill_and_shadow_on_a_shape():
    grad = {"type": "linear", "angle_deg": 90, "stops": [{"colour": "#FF0000", "at": 0, "alpha_pct": 100},
                                                        {"colour": "#0000FF", "at": 100, "alpha_pct": 100}]}
    out = render([layer("shape", 10, 10, 30, 30, shape="rect", fill_gradient=grad,
                        shadow={"dx_mm": 2, "dy_mm": 2, "blur_mm": 0, "colour": "#000000", "opacity_pct": 100})])
    assert pixel(out, 11, 25)[0] > 200 and pixel(out, 39, 25)[2] > 200
    assert pixel(out, 41, 41)[0] < 60  # the hard shadow peeks out bottom-right


def test_image_layer_mask_zoom_and_outline():
    from apps.card_designs.models import CardDesignAsset  # noqa: F401  (assets reach the renderer through the context)
    asset = uid()
    doc = normalize_document(document([layer("image", 10, 10, 30, 30, asset_id=asset, fit="cover", mask="circle",
                                             outline={"width_mm": 1, "colour": "#FFAA00"})]),
                             asset_colours={asset: "#B42828"}, check_contrast=False)
    out = render_png(doc, RenderContext(assets={asset: png((40, 40))}))
    assert close(pixel(out, 25, 25), (180, 40, 40), 20)            # the image fills the circle
    assert close(pixel(out, 10.4, 10.4), (255, 255, 255), 10)      # outside the circle: background
    assert close(pixel(out, 25, 9.5), (255, 170, 0), 40)           # the outline ring sits just outside the edge


def test_cutout_variant_uses_the_cutout_and_the_sticker_outline_follows_the_alpha_edge():
    photo = layer("photo", 10, 10, 30, 40, shape="square", variant="cutout",
                  outline={"width_mm": 1.5, "colour": "#FF00FF"})
    out = render([photo], RenderContext(photo=png((60, 80), (200, 30, 30, 255)), photo_cutout=silhouette(),
                                        values={"name": "A B"}))
    centre = pixel(out, 25, 30)
    assert close(centre, (20, 20, 200))                         # the cut-out block, not the red original
    assert close(pixel(out, 11, 11), (255, 255, 255), 10)       # transparent corner of the cut-out shows the card
    # the block spans x 17.5-32.5 mm, y 20-40 mm; the outline is ~1.5 mm outside that alpha edge
    assert close(pixel(out, 16.6, 30), (255, 0, 255), 45)
    assert close(pixel(out, 14, 30), (255, 255, 255), 10)       # beyond the outline: background again


def test_cutout_falls_back_to_the_original_when_missing_or_stale():
    photo = layer("photo", 10, 10, 30, 40, shape="square", variant="cutout")
    original = png((60, 80), (200, 30, 30, 255))
    for context in (RenderContext(photo=original, photo_cutout=None),   # none ready / stale / switch off
                    RenderContext(photo=original)):
        assert close(pixel(render([photo], context), 25, 30), (200, 30, 30))


def test_auto_variant_follows_the_holders_choice():
    photo = layer("photo", 10, 10, 30, 40, shape="square", variant="auto")
    original, cutout = png((60, 80), (200, 30, 30, 255)), silhouette()
    chosen = render([photo], RenderContext(photo=original, photo_cutout=cutout, use_cutout=True))
    declined = render([photo], RenderContext(photo=original, photo_cutout=cutout, use_cutout=False))
    assert close(pixel(chosen, 25, 30), (20, 20, 200)) and close(pixel(declined, 25, 30), (200, 30, 30))


def test_original_variant_ignores_a_ready_cutout():
    photo = layer("photo", 10, 10, 30, 40, shape="square", variant="original")
    out = render([photo], RenderContext(photo=png((60, 80), (200, 30, 30, 255)), photo_cutout=silhouette(), use_cutout=True))
    assert close(pixel(out, 25, 30), (200, 30, 30))


def test_photo_arch_mask_and_zoom_pan():
    photo = layer("photo", 10, 10, 30, 40, shape="arch", zoom=2, focal_x_pct=0, focal_y_pct=0)
    out = render([photo], RenderContext(photo=png((60, 80), (30, 160, 30, 255))))
    assert close(pixel(out, 25, 40), (30, 160, 30), 20)
    assert close(pixel(out, 10.6, 10.6), (255, 255, 255), 10)  # the arch's rounded top leaves the corner empty


def test_flip_mirrors_a_cutout():
    from PIL import Image as PI
    asym = PI.new("RGBA", (60, 80), (0, 0, 0, 0))
    asym.paste((20, 20, 200, 255), (0, 0, 20, 80))
    buffer = BytesIO()
    asym.save(buffer, format="PNG")
    base = dict(shape="square", variant="cutout")
    left = render([layer("photo", 10, 10, 30, 40, **base)], RenderContext(photo_cutout=buffer.getvalue()))
    flipped = render([layer("photo", 10, 10, 30, 40, flip_x=True, **base)], RenderContext(photo_cutout=buffer.getvalue()))
    assert close(pixel(left, 13, 30), (20, 20, 200)) and close(pixel(left, 37, 30), (255, 255, 255), 10)
    assert close(pixel(flipped, 37, 30), (20, 20, 200)) and close(pixel(flipped, 13, 30), (255, 255, 255), 10)


def test_rich_text_plan_two_weights_one_name_and_highlight_bars():
    spans = [{"text": "{{first_name}}\n", "font_family": "Gilroy Light", "font_weight": 300},
             {"text": "{{last_name}}", "font_family": "Gilroy ExtraBold", "font_weight": 800}]
    row = normalize_document(document([layer("text", 3, 10, 48, 20, text="", spans=spans, font_size_pt=18, line_height=1.0,
                                             uppercase=True, highlight={"colour": "#DFFF8F"}, valign="top")]),
                             check_contrast=False)["front"]["layers"][0]
    resolved = rendering_rich.resolve(row, RenderContext(values={"name": "Fathima Shenza"}))
    assert [span["text"] for span in resolved] == ["FATHIMA\n", "SHENZA"]
    from reportlab.lib.units import mm
    plan = rendering_rich.plan(resolved, row, row["w_mm"] * mm, row["h_mm"] * mm)
    assert ["".join(part["text"] for part in line["parts"]) for line in plan["lines"]] == ["FATHIMA", "SHENZA"]
    assert len(plan["bars"]) == 2 and plan["bars"][0]["w"] > plan["lines"][0]["width"]
    assert plan["lines"][1]["baseline"] > plan["lines"][0]["baseline"] and plan["scale"] == 1.0


def test_rich_text_wraps_and_shrinks_with_one_scale_for_every_span():
    row = normalize_document(document([layer("text", 3, 10, 30, 8, text="", font_size_pt=20, spans=[
        {"text": "Community hardware "}, {"text": "hackathon night", "font_weight": 700, "size_scale": 1.5}])]),
        check_contrast=False)["front"]["layers"][0]
    from reportlab.lib.units import mm
    plan = rendering_rich.plan(rendering_rich.resolve(row, RenderContext()), row, row["w_mm"] * mm, row["h_mm"] * mm)
    assert plan["scale"] < 1.0
    sizes = {round(line["size"] / plan["scale"], 1) for line in plan["lines"]}
    assert sizes <= {20.0, 30.0}


def test_rich_text_paints_highlight_underline_stroke_and_shadow():
    text = layer("text", 6, 20, 42, 10, text="MENTOR", font_weight=700, font_size_pt=14, colour="#142C2A", align="center",
                 highlight={"colour": "#DFFF8F", "pad_x_mm": 2, "pad_y_mm": 1, "radius_mm": 0},
                 underline={"colour": "#FF0000", "thickness_pt": 2, "offset_pt": 3},
                 stroke={"colour": "#0000FF", "width_pt": 0.8},
                 shadow={"dx_mm": 1, "dy_mm": 1, "blur_mm": 0, "colour": "#808080", "opacity_pct": 100})
    out = render([text])
    from reportlab.lib.units import mm
    row = normalize_document(document([text]), check_contrast=False)["front"]["layers"][0]
    bar = rendering_rich.plan(rendering_rich.resolve(row, RenderContext()), row, row["w_mm"] * mm, row["h_mm"] * mm)["bars"][0]
    left = row["x_mm"] + bar["x"] / mm + 0.5                       # inside the bar's left padding, before the first glyph
    middle = row["y_mm"] + (bar["y"] + bar["h"] / 2) / mm
    assert close(pixel(out, left, middle), (223, 255, 143), 20)    # the highlight colour


def test_translations_pick_the_context_locale():
    text = layer("text", 3, 10, 48, 10, text="Hello", font_size_pt=16, colour="#000000", translations={"ml": "{{name}}"})
    row = normalize_document(document([text]), check_contrast=False)["front"]["layers"][0]
    assert rendering_rich.resolve(row, RenderContext(values={"name": "X"}, locale="ml"))[0]["text"] == "X"
    assert rendering_rich.resolve(row, RenderContext(values={"name": "X"}, locale="fr"))[0]["text"] == "Hello"


def test_text_honours_its_opacity_in_print():
    solid = render([layer("text", 5, 10, 44, 20, text="W", font_family="Outfit", font_weight=800, font_size_pt=90,
                          colour="#000000", align="center", valign="middle")])
    faint = render([layer("text", 5, 10, 44, 20, text="W", font_family="Outfit", font_weight=800, font_size_pt=90,
                          colour="#000000", align="center", valign="middle", opacity=30)])
    assert min(Image.open(BytesIO(solid)).convert("L").crop((20, 100, 400, 330)).getdata()) < 40
    assert min(Image.open(BytesIO(faint)).convert("L").crop((20, 100, 400, 330)).getdata()) > 140


def test_hidden_groups_do_not_print():
    group = uid()
    layers = [layer("shape", 5, 5, 20, 20, shape="rect", fill="#000000", group=group),
              layer("shape", 30, 5, 20, 20, shape="rect", fill="#000000", group=group)]
    doc = document(layers)
    doc["front"]["groups"] = [{"id": group, "name": "g", "hidden": True}]
    out = render_png(normalize_document(doc, check_contrast=False), RenderContext())
    assert close(pixel(out, 15, 15), (255, 255, 255), 5)


def test_guides_never_print():
    plain = render([layer("shape", 5, 5, 20, 20, shape="rect", fill="#006E63")])
    guided = render([layer("shape", 5, 5, 20, 20, shape="rect", fill="#006E63")],
                    guides={"punch_slot": {"shape": "slot", "x_mm": 21, "y_mm": 3, "w_mm": 12, "h_mm": 3},
                            "rulers": [{"axis": "x", "at_mm": 10}], "safe_mm": 6, "margin_mm": 5})
    assert plain == guided


def test_geometry_helpers_match_the_documented_rules():
    left, top, width, height = studio_geometry.place(600, 800, 40, 42, "cover", 1, 50, 50)
    assert (round(width, 2), round(height, 2)) == (40.0, 53.33) and round(top, 2) == -5.67 and left == 0
    assert studio_geometry.place(600, 800, 40, 42, "stretch")[2:] == (40.0, 42.0)
    assert studio_geometry.place(600, 800, 40, 42, "contain", 1, 0, 0)[:2] == (0.0, 0.0)
    assert studio_geometry.arch_radius(30, 40) == 15 and studio_geometry.arch_radius(30, 10) is None
    assert studio_geometry.shadow_pad_mm({"outline": {"width_mm": 1}, "shadow": {"dx_mm": 1, "dy_mm": -2, "blur_mm": 2}}) == 6.0


def test_the_sticker_outline_grows_the_silhouette_by_the_requested_distance():
    from apps.card_designs.rendering_media import sticker
    image = Image.new("L", (200, 200), 0)
    image.paste(255, (80, 80, 120, 120))
    grown = sticker(image, 20)
    row = [grown.getpixel((x, 100)) for x in range(200)]
    left_edge = next(index for index, value in enumerate(row) if value > 128)
    assert 56 <= left_edge <= 64  # 80 - 20 = 60, within a few px
    assert row[0] == 0 and row[199] == 0


def test_cards_resolve_the_cutout_only_when_a_photo_layer_asks_for_it(monkeypatch):
    from apps.card_designs import cards, cutouts
    asked = []
    monkeypatch.setattr(cutouts, "photo_variant_bytes", lambda kind, card, variant="auto": asked.append(variant) or b"PNG")
    monkeypatch.setattr(cutouts, "owner", lambda kind, card: None)
    plain = normalize_document(document([layer("photo", 1, 1, 10, 10)]), check_contrast=False)
    asking = normalize_document(document([layer("photo", 1, 1, 10, 10, variant="auto")]), check_contrast=False)
    assert cards.cutout_for("member_card", object(), plain) == (None, False) and asked == []
    assert cards.cutout_for("member_card", object(), asking) == (b"PNG", False) and asked == ["cutout"]

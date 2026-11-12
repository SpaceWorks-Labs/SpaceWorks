"""Lossless migration: a stored v2 certificate renders IDENTICALLY through the old and the shared paths (decision 315).

Each v2 layout is drawn twice onto a recording canvas - once by the old renderer (`layer_rendering.draw_document`), once by
`certificate_compile.compile_v2` + the shared `draw_side` with the v2 text metrics - and the text (string, position, size,
colour), image, line and rectangle operations are compared. Preview mode keeps the QR a dummy so the code itself is not
involved; the QR pattern parity is checked separately.
"""
import hashlib
import importlib.util
import json
from copy import deepcopy
from pathlib import Path

import pytest
from reportlab.lib.units import mm
from rest_framework.exceptions import ValidationError

from apps.card_designs import certificate_compile, rendering_text
from apps.card_designs.certificate_compile import NotCompilable, compile_v2
from apps.card_designs.rendering import RenderContext, draw_side
from apps.events.certificates.layer_rendering import ImageResource, QrResource, SignatureResource, draw_document
from apps.events.certificates.layout import COLOURS

from .helpers import png, uid
from .recording import Recorder, comparable, same

REPO = Path(__file__).resolve().parents[4]
FIXTURES = REPO / "backend" / "apps" / "card_designs" / "fixtures"
OLD_VALUES = {"name": "Fathima Shenza", "event": "Community Hardware Hackathon 2026", "eventDate": "14 November 2026",
              "organisation": "Tinkerspace", "issueDate": "2 December 2026", "certificate_id": "SW-2026-000042",
              "kind": "Winner", "award": "1st place - Best hardware hack", "role": "Participant", "place": "1st place",
              "crewRole": "Participant"}
IMAGE_BYTES = png()
IMAGE_SHA = hashlib.sha256(IMAGE_BYTES).hexdigest()


def _script():
    spec = importlib.util.spec_from_file_location("export_studio_fixtures", REPO / "scripts" / "export_studio_fixtures.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _layouts():
    layouts, normalize = _script()._certificate_layouts()
    wide = deepcopy(layouts["wide"])
    wide["layers"].append({"id": uid(), "order": len(wide["layers"]), "type": "image", "x_mm": 240, "y_mm": 20,
                           "width_mm": 40, "height_mm": 30, "rotation": 0, "opacity": 0.8, "resource_id": uid()})
    layouts = {**layouts, "wide-with-image": wide}
    return {name: normalize(layout) for name, layout in layouts.items()}


def _new_values(old):
    return {**old, "recipient": old["name"], "event_date": old["eventDate"], "issue_date": old["issueDate"],
            "serial": old["certificate_id"], "serial_short": old["certificate_id"][:8].upper()}


def _old_ops(layout):
    def resolver(layer):
        if layer["type"] == "certificate_qr":
            return QrResource("x", dummy=True)
        if layer["type"] == "signature":
            return SignatureResource("Dr Director", "Director", ImageResource(IMAGE_BYTES, IMAGE_SHA))
        if layer["type"] == "image":
            return ImageResource(IMAGE_BYTES, IMAGE_SHA)
        return None
    recorder = Recorder()
    draw_document(recorder, layout, OLD_VALUES, resolver, preview=True)
    return recorder.ops


def _new_ops(layout):
    document = compile_v2(layout, {"merge": {"role": "Participant"}})
    assets = {layer["resource_id"]: IMAGE_BYTES for layer in layout["layers"] if layer["type"] == "image"}
    context = RenderContext(values=_new_values(OLD_VALUES), verify_qr="x", preview=True, assets=assets,
                            signatories={1: {"name": "Dr Director", "title": "Director", "image": IMAGE_BYTES, "approved": True}})
    recorder = Recorder()
    draw_side(recorder, document, "front", context)
    return recorder.ops


def _page(layout):
    return layout["page_width_mm"] * mm, layout["page_height_mm"] * mm


@pytest.mark.parametrize("name", ["wide", "legacy-labels", "wide-with-image"])
def test_old_and_shared_render_paths_draw_the_same_thing(name):
    layout = _layouts()[name]
    old, new = comparable(_old_ops(layout), _page(layout)), comparable(_new_ops(layout), _page(layout))
    assert old, "the layout drew nothing"
    assert same(old, new), f"old {old}\nnew {new}"


def test_the_compiled_document_maps_every_v2_layer():
    layout = _layouts()["wide"]
    document = compile_v2(layout, {"merge": {"role": "Participant"}})
    assert document["kind"] == "certificate" and document["source"] == {"kind": "certificate_v2"}
    assert document["front"]["page_width_mm"] == 297.0 and document["back"]["layers"] == []
    by_order = sorted(layout["layers"], key=lambda row: row["order"])
    assert [row["id"] for row in document["front"]["layers"]] == [row["id"] for row in by_order]
    assert {row["kind"] for row in document["front"]["layers"]} == {"text", "signature", "verify_qr", "certificate_id"}
    signature = next(row for row in document["front"]["layers"] if row["kind"] == "signature")
    assert signature["signatory_slot"] == 1 and signature["rule"]["width_pt"] == 0.6
    name = next(row for row in document["front"]["layers"] if row.get("text") == "{{name}}")
    assert name["colour"] == COLOURS["teal"]


def test_camel_case_tags_and_opacity_are_mapped():
    layout = _layouts()["wide"]
    layout["layers"][3]["opacity"] = 0.5
    row = compile_v2(layout, {"merge": {"role": "Participant"}})["front"]["layers"][3]
    assert row["text"] == "{{event_date}} - issued {{issue_date}} by {{organisation}}" and row["opacity"] == 50.0


def test_crew_role_prints_nothing_before_labels_were_frozen_and_the_role_after():
    layout = _layouts()["wide"]
    frozen = compile_v2(layout, {"merge": {"role": "Participant"}})["front"]["layers"][4]["text"]
    legacy = compile_v2(layout, {})["front"]["layers"][4]["text"]
    assert frozen == "Role: {{role}} / {{role}} / {{award}} {{place}}"
    assert legacy == "Role:  / {{role}} / {{award}} {{place}}"


def test_a_v1_legacy_background_design_is_not_compilable_and_stays_on_the_old_renderer():
    with pytest.raises(NotCompilable):
        compile_v2({**_layouts()["wide"], "legacy_background": True})
    with pytest.raises(NotCompilable):
        compile_v2({"version": 1, "layers": []})


def test_the_colour_tokens_match_the_v2_table():
    assert certificate_compile.TOKENS == COLOURS


def test_v2_overflow_still_raises_instead_of_clipping():
    layout = _layouts()["wide"]
    layout["layers"][2].update(shrink_to_fit=False, font_size_pt=96, text="{{event}} {{event}} {{event}}")
    with pytest.raises(ValidationError):
        _new_ops(layout)
    with pytest.raises(ValidationError):
        _old_ops(layout)


def test_fit_compat_shrinks_in_half_point_steps_and_never_clips():
    layer = {"font_family": "Outfit", "font_weight": 700, "font_size_pt": 40, "line_height": 1.3, "shrink_to_fit": True,
             "tracking_pt": 0, "uppercase": False, "align": "left"}
    size, lines = rendering_text.fit_compat("A very long certificate event title that cannot fit on one line", layer, 300, 60)
    assert size < 40 and (40 - size) % 0.5 == 0 and len(lines) * size * 1.3 <= 60


def test_the_preview_qr_keeps_the_v2_dummy_pattern():
    layout = _layouts()["wide"]
    old = [op for op in comparable(_old_ops(layout), _page(layout)) if op[0] == "rect"]
    new = [op for op in comparable(_new_ops(layout), _page(layout)) if op[0] == "rect"]
    assert old and same(old, new)


def _guard(name, producer):
    path = FIXTURES / name
    if not path.exists():
        pytest.skip(f"{name} is generated by: python scripts/export_studio_fixtures.py")
    assert path.read_text(encoding="utf-8") == json.dumps(producer(), indent=1, sort_keys=True) + "\n", \
        "run: python scripts/export_studio_fixtures.py"


def test_the_compat_fixture_matches_the_server_code():
    _guard("certificate_compat_cases.json", _script().certificate_compat_cases)


def test_the_plan_fixture_matches_the_server_code():
    _guard("certificate_plan_cases.json", _script().certificate_plan_cases)

"""Original source inventory and the E/ARTWORK frozen seed contract."""

import ast
import hashlib
import json
from pathlib import Path
import re
from uuid import UUID
from xml.etree import ElementTree as ET

from jsonschema import Draft202012Validator, FormatChecker
import pytest

from apps.events.default_templates import (
    BADGE_SEEDS, CERTIFICATE_SEEDS, badge_seed, certificate_seed,
    iter_badge_stock_seeds,
)
from apps.events.default_templates.manifest import ARTWORK, PALETTES, STOCKS

ROOT = Path(__file__).resolve().parents[5]
TEMPLATES = ROOT / "backend/apps/events/default_templates"
ILLUSTRATIONS = ROOT / "frontend/src/assets/illustrations"
CONTRACTS = Path(__file__).parents[1] / "contracts/fixtures"
FROZEN = json.loads((CONTRACTS / "template-seed-v2.json").read_text())
SCHEMA = json.loads((CONTRACTS / "contract-schemas-v3.json").read_text())
ALL_SEEDS = [*CERTIFICATE_SEEDS, *iter_badge_stock_seeds()]


def test_exact_inventory_and_checksums_have_no_unregistered_artwork():
    files = {item["path"] for item in ARTWORK}
    assert files == {str(p.relative_to(TEMPLATES)).replace("\\", "/")
                     for p in (TEMPLATES / "artwork").glob("*.svg")}
    assert len(files) == FROZEN["counts"]["packaged_svg"] == 12
    assert len(list(ILLUSTRATIONS.rglob("*.svg"))) == 58
    assert len({re.sub(r"\.(light|dark)\.svg$", "", p) for p in files}) == 6
    assert len(CERTIFICATE_SEEDS) == 6
    assert len(BADGE_SEEDS) == 6
    assert len(list(iter_badge_stock_seeds())) == 36
    assert {k: list(v) for k, v in STOCKS.items()} == FROZEN["stocks"]
    for item in ARTWORK:
        data = (TEMPLATES / item["path"]).read_bytes()
        assert hashlib.sha256(data).hexdigest() == item["sha256"]


def test_all_svg_are_safe_self_contained_and_theme_approved():
    allowed_tags = {"svg", "g", "path", "rect", "circle"}
    for file in [*ILLUSTRATIONS.rglob("*.svg"), *(TEMPLATES / "artwork").glob("*.svg")]:
        source = file.read_text()
        assert "<!" not in source and "url(" not in source
        root = ET.fromstring(source)
        assert root.attrib["viewBox"].startswith("0 0 ")
        assert root.attrib["aria-hidden"] == "true"
        assert root.attrib["focusable"] == "false"
        palette = set(PALETTES[file.stem.rsplit(".", 1)[1]].values())
        assert set(re.findall(r"#[\da-fA-F]{6}", source)) <= palette
        for element in root.iter():
            assert element.tag.rsplit("}", 1)[-1] in allowed_tags
            assert all(not key.lower().startswith("on") and "href" not in key
                       for key in element.attrib)


@pytest.mark.parametrize("seed", ALL_SEEDS, ids=lambda s: (
    s["seed_id"] + "." + s["theme"] + "." + s.get("stock", "a4-landscape")))
def test_seed_geometry_resources_and_shared_schema(seed):
    Draft202012Validator({**SCHEMA, "$ref": "#/$defs/TemplateDocumentV2"},
                         format_checker=FormatChecker()).validate(seed["document"])
    document = seed["document"]
    layers = document["layers"]
    assert len(layers) <= FROZEN["max_layers"]
    assert [layer["order"] for layer in layers] == list(range(len(layers)))
    assert len({UUID(layer["id"]) for layer in layers}) == len(layers)
    assert sum(layer.get("font_family") == "Unbounded" for layer in layers) == 1
    resources = {r["id"]: r for r in seed["resources"]}
    for resource in resources.values():
        assert set(resource) == {"id", "kind", "path", "sha256"}
        assert resource["kind"] == "packaged_artwork"
        assert resource["path"] in {item["path"] for item in ARTWORK}
        assert hashlib.sha256((TEMPLATES / resource["path"]).read_bytes()).hexdigest() == resource["sha256"]
    for layer in layers:
        assert layer["rotation"] == 0
        assert layer["x_mm"] + layer["width_mm"] <= document["page_width_mm"]
        assert layer["y_mm"] + layer["height_mm"] <= document["page_height_mm"]
        assert "http" not in json.dumps(layer)
        if layer["type"] == "text":
            assert layer["shrink_to_fit"]
            assert layer["font_size_pt"] >= 6
            assert set(re.findall(r"{{(.*?)}}", layer["text"])) <= set(FROZEN["text_tags"])
            assert layer["colour_token"] == "ink"
        if layer["type"] == "image":
            assert layer["resource_id"] in resources
        if layer["type"].endswith("_qr"):
            assert layer["width_mm"] == layer["height_mm"] >= 21
    # All non-background boxes are disjoint: no stock relies on hiding overflow.
    content = [layer for layer in layers if layer["type"] != "image"]
    for index, first in enumerate(content):
        for second in content[index + 1:]:
            assert (first["x_mm"] + first["width_mm"] <= second["x_mm"]
                    or second["x_mm"] + second["width_mm"] <= first["x_mm"]
                    or first["y_mm"] + first["height_mm"] <= second["y_mm"]
                    or second["y_mm"] + second["height_mm"] <= first["y_mm"])
    slots = {layer.get("resource_slot") for layer in layers}
    if seed["seed_id"].startswith("badge-"):
        assert {"selected_member_photo", "logo", "event_credential_qr"} <= slots
        assert seed["no_photo_fallback"] == "placeholder"
    else:
        assert {"logo", "certificate_verification_qr"} <= slots
        assert any(layer["type"] == "certificate_id" for layer in layers)


def test_fixture_is_current_fresh_data_and_installation_is_not_implicit():
    fixtures = json.loads((TEMPLATES / "schema_fixtures.json").read_text())
    assert fixtures["certificates"] == list(CERTIFICATE_SEEDS)
    assert fixtures["badges"] == list(iter_badge_stock_seeds())
    assert fixtures["schema_ref"] == FROZEN["schema_ref"]
    assert fixtures["install"] == FROZEN["install"]
    first = badge_seed("classic", "light")
    first["document"]["layers"].clear()
    assert badge_seed("classic", "light")["document"]["layers"]
    first = certificate_seed("foundry", "light")
    first["resources"].clear()
    assert certificate_seed("foundry", "light")["resources"]
    for file in TEMPLATES.glob("*.py"):
        tree = ast.parse(file.read_text())
        imports = [node for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)]
        assert all(not (node.module or "").startswith(("django", "apps.")) for node in imports)


@pytest.mark.parametrize("builder,args", [
    (certificate_seed, ("unknown", "light")),
    (certificate_seed, ("foundry", "system")),
    (badge_seed, ("classic", "light", "a6-landscape")),
    (badge_seed, ("classic", "system")),
])
def test_unknown_selection_fails_closed(builder, args):
    with pytest.raises(ValueError):
        builder(*args)

"""SWITCH-MATRIX: the backend registry, the frontend catalogue and the docs say the same thing.

Generated from the live registries, so a module or feature added later is compared without editing this file:
keys, labels, parents and defaults agree between `module_registry`/`FEATURES`, `frontend/src/lib/moduleLabels.ts`,
`frontend/src/lib/featureDefinitions/part*.ts`, the generated `ModulesEnum`, `docs/MODULES.md` and `docs/MODULES-OFF.md`.
"""

import pathlib
import re

import pytest

from apps.makerspaces.capabilities import FEATURES
from apps.makerspaces.module_registry import BY_KEY, MODULE_KEYS, core_module_keys

ROOT = pathlib.Path(__file__).resolve().parents[3]
FE = ROOT / "frontend" / "src"
DOCS = ROOT / "docs"
OFF = (DOCS / "MODULES-OFF.md").read_text(encoding="utf-8")
MODULES_MD = "".join(p.read_text(encoding="utf-8") for p in sorted(DOCS.glob("MODULES*.md")))
CORE = core_module_keys()


def _frontend_features():
    rows = {}
    for part in sorted((FE / "lib" / "featureDefinitions").glob("part*.ts")):
        for line in part.read_text(encoding="utf-8").splitlines():
            m = re.search(r'\{ key: "([a-z_.0-9]+)", parent_module: (null|"[a-z_]+"), label: t`(.*?)` ', line)
            if m:
                rows[m[1]] = (None if m[2] == "null" else m[2].strip('"'), m[3])
    return rows


def _frontend_module_labels():
    text = (FE / "lib" / "moduleLabels.ts").read_text(encoding="utf-8").split("const MODULE_NAMES", 1)[1]
    return dict(re.findall(r"(\w+): t`([^`]*)`", text.split("});", 1)[0]))


FE_FEATURES = _frontend_features()
FE_LABELS = _frontend_module_labels()


def test_the_frontend_catalogue_has_exactly_the_backend_features():
    assert set(FE_FEATURES) == set(FEATURES)


@pytest.mark.parametrize("key", sorted(FEATURES))
def test_feature_parent_and_label_agree_with_the_frontend(key):
    parent, label = FE_FEATURES[key]
    assert parent == FEATURES[key].parent_module, key
    assert label == FEATURES[key].label, key


@pytest.mark.parametrize("key", sorted(MODULE_KEYS))
def test_module_label_agrees_with_the_frontend(key):
    assert FE_LABELS.get(key) == BY_KEY[key].label


def test_the_generated_modules_enum_is_exactly_the_registry():
    api = (FE / "generated" / "api.ts").read_text(encoding="utf-8")
    declared = re.search(r"export type ModulesEnum = ([^;]+);", api)[1]
    assert set(re.findall(r'"([a-z_]+)"', declared)) == set(MODULE_KEYS)


@pytest.mark.parametrize("key", sorted(MODULE_KEYS))
def test_every_module_has_a_reference_section_and_an_off_row(key):
    assert re.search(rf"^### {re.escape(key)}\b", MODULES_MD, re.M) or f"`{key}`" in MODULES_MD, key
    row = re.search(rf"^\| `{re.escape(key)}` \| (.*)$", OFF, re.M)
    assert row, f"MODULES-OFF.md has no row for {key}"
    if key in CORE:
        assert "Core module" in row[1], f"{key} is core but its off row does not say it cannot be uninstalled"
    else:
        assert "Core module" not in row[1], f"{key} is optional but its off row calls it core"


def _default_marks():
    """{feature: [marked?]} from every table in MODULES.md that has a Default column."""
    marks, default_col = {}, None
    for line in (DOCS / "MODULES.md").read_text(encoding="utf-8").splitlines():
        if not line.startswith("|"):
            default_col = None
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if "Default" in cells:
            default_col = cells.index("Default")
            continue
        m = re.fullmatch(r"`([a-z_.0-9]+)`", cells[0])
        if m and default_col is not None and default_col < len(cells):
            marks.setdefault(m[1], []).append("●" in cells[default_col])
    return marks


MARKS = _default_marks()


@pytest.mark.parametrize("key", sorted(k for k in FEATURES if FEATURES[k].default_enabled))
def test_a_default_on_feature_is_marked_default_in_the_docs(key):
    assert key in MARKS, f"no table row with a Default column for {key} in docs/MODULES.md"
    assert all(MARKS[key]), f"{key} is on by default in code but docs/MODULES.md does not mark it"


@pytest.mark.parametrize("key", sorted(k for k in FEATURES if not FEATURES[k].default_enabled and k in MARKS))
def test_a_default_off_feature_is_not_marked_default_in_the_docs(key):
    assert not any(MARKS[key]), f"{key} is off by default in code but docs/MODULES.md marks it on"

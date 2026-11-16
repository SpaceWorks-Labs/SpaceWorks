"""The TypeScript mirror (frontend/src/lib/brandColours.ts) is tested against this same fixture."""

import json
from pathlib import Path

import pytest

from apps.makerspaces.theme_contrast import derive_palette

FIXTURE = Path(__file__).resolve().parents[3] / "frontend" / "src" / "lib" / "fixtures" / "themeContrastCases.json"
CASES = json.loads(FIXTURE.read_text(encoding="utf-8"))


@pytest.mark.parametrize("case", CASES, ids=lambda case: json.dumps(case["theme"]))
def test_derive_palette_matches_the_shared_frontend_fixture(case):
    for mode in ("light", "dark"):
        palette, expected = derive_palette(case["theme"], mode), case[mode]
        for key in ("fill", "foreground", "hover", "active", "soft", "ink"):
            assert list(palette[key]) == expected[key], (mode, key)
        assert [name for name, _, _ in palette["pairs"]] == [row[0] for row in expected["pairs"]]
        for (_, ratio, minimum), row in zip(palette["pairs"], expected["pairs"]):
            assert ratio == pytest.approx(row[1], abs=1e-5)
            assert minimum == row[2]

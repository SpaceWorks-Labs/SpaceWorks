"""Write frontend/src/features/auth/sampleCard.generated.json: the sample staff ID card on the sign-in screens.

The document is built by the REAL card generator (apps.card_designs.default_templates.build, domain
"staff_cards": the Aurora look re-labelled for staff, with the STAFF band), then given the one edit a space
makes in the designer: a logo tile in the header band, with the space name moved beside it, and the footer line.
Aurora itself ships in the brand palette (Teal header, Citron ribbon, Orange tail, Cream body, Ink text).
Regenerate with:  python scripts/export_sample_card.py
Django need not be installed: the generator only uses gettext at import time, which is stubbed here.
The guard test backend/tests/parity_0120/sample_card/test_sample_card_fixture.py fails if the file drifts.
"""
import json
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
try:
    import django  # noqa: F401
except ImportError:  # plain python: stub the one import the templates make
    for name in ("django", "django.utils", "django.utils.translation"):
        sys.modules[name] = types.ModuleType(name)
    sys.modules["django.utils.translation"].gettext = lambda text: text
from apps.card_designs.default_templates import TEMPLATES  # noqa: E402
from apps.card_designs.default_templates.staff import staff_document  # noqa: E402
from apps.card_designs.default_templates.builders import Builder  # noqa: E402

LOOK = "aurora"  # the most distinctive shipped look: teal header, citron ribbon, cream card
OUT = ROOT / "frontend" / "src" / "features" / "auth" / "sampleCard.generated.json"


TEAL = "#006E63"  # the footer line: Teal labels on Warm Cream are 5.6:1


def sample_document():
    # What default_templates.build(LOOK, "staff_cards", "light") does, minus its DRF validation import.
    document = staff_document(TEMPLATES[LOOK]("staff_cards", "light"), "light")
    logo = Builder("sample-card").logo("Space logo", "space", 3, 1, 8, 8, tile=True).layers[0]
    layers = []
    for layer in document["front"]["layers"]:
        layers.append({**layer, "x_mm": 14, "w_mm": 58} if layer["name"] == "Space name" else layer)
        if layer["name"] == "Aurora tail":
            layers.append(logo)
    # Aurora has no organisation line: add the footer Classic uses (the same text layer a space would add).
    layers.append(Builder("sample-card").text("Footer", "{{organisation}}", 5, 45.8, 54, 3.5, size=6, weight=500,
                                              colour=TEAL).layers[0])
    return {**document, "front": {**document["front"], "layers": layers}}


def main():
    text = json.dumps(sample_document(), indent=1, sort_keys=True) + "\n"
    OUT.write_text(text, encoding="utf-8", newline="\n")
    print("wrote", OUT.relative_to(ROOT))


if __name__ == "__main__":
    main()

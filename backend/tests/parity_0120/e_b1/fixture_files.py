"""The golden badge fixtures shared with the TypeScript suite (written by E-B1, read-only for E-F1)."""
import json
from pathlib import Path

FIXTURES = Path(__file__).resolve().parents[3] / "apps" / "card_designs" / "fixtures"


def load(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))

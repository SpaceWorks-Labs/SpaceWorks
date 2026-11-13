"""O-B4 guard: card fonts stay free (OFL / Apache / UFL); no commercial Gilroy ships (decision 219(a))."""
import json
import re
from pathlib import Path

from apps.card_designs import fonts

REPO = Path(__file__).resolve().parents[4]
COMMERCIAL_GILROY = re.compile(r"^Gilroy-(Regular|Medium|SemiBold|Bold)\.(otf|ttf|woff2?)$", re.I)
SKIP = {"node_modules", ".git", ".venv", "venv", "__pycache__"}


def test_brand_families_are_outfit_unbounded_and_the_studio_open_faces():
    assert set(fonts.BRAND) == {"Outfit", "Unbounded", "Bebas Neue", "Pacifico", "DM Serif Display"}  # Card Studio, 314


def test_catalogue_is_the_google_open_licence_catalogue():
    path = Path(fonts.__file__).with_name("font_catalog.json")
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["source"] == "fonts.google.com/metadata/fonts"  # Google Fonts ships only OFL/Apache/UFL families
    assert not any(row[0].lower().startswith("gilroy") for row in data["families"])


def test_shipped_brand_faces_carry_their_open_licence():
    for family in fonts.BRAND:
        assert (fonts.STUDIO_DIR / f"OFL-{family.replace(' ', '')}.txt").is_file() or (fonts.BRAND_DIR / f"OFL-{family}.txt").is_file()


def test_no_commercial_gilroy_weights_anywhere_in_the_repo():
    found = []
    for root, dirs, files in __import__("os").walk(REPO):
        dirs[:] = [name for name in dirs if name not in SKIP]
        found += [name for name in files if COMMERCIAL_GILROY.match(name)]
    assert found == []

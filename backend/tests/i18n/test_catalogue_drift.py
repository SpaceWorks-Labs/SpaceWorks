"""The committed English catalogue matches a fresh makemessages run (msgids only)."""
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[2]
PO = BACKEND / "locale/en/LC_MESSAGES/django.po"
MAKEMESSAGES = [sys.executable, "manage.py", "makemessages", "-l", "en", "--no-obsolete", "--no-location",
                "--ignore=tests/*", "--ignore=staticfiles/*", "--ignore=scripts/*"]


def _canonical_catalogue(path):
    text = subprocess.check_output(
        ["msgcat", "--no-wrap", "--sort-output", str(path)], encoding="utf-8",
    )
    return "".join(
        line for line in text.splitlines(keepends=True)
        if not line.startswith('"POT-Creation-Date: ')
    )


@pytest.mark.skipif(
    not all(shutil.which(command) for command in ("xgettext", "msgcat")),
    reason="GNU gettext is not installed",
)
def test_committed_po_has_every_extracted_message(tmp_path):
    original = PO.read_bytes()
    committed = tmp_path / "committed.po"
    committed.write_bytes(original)
    try:
        subprocess.run(MAKEMESSAGES, cwd=BACKEND, check=True, capture_output=True)
        fresh = _canonical_catalogue(PO)
    finally:
        PO.write_bytes(original)
    assert fresh == _canonical_catalogue(committed)


def test_english_catalogue_is_the_only_one():
    assert sorted(p.name for p in (BACKEND / "locale").iterdir()) == ["en"]
    assert "msgid" in PO.read_text(encoding="utf-8")

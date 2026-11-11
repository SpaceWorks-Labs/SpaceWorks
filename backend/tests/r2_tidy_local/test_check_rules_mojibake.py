"""scripts/ci/check_rules.py rule 4: no double-encoded UTF-8 (mojibake) in tracked text files."""
import importlib.util
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location("check_rules", REPO / "scripts" / "ci" / "check_rules.py")
rules = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rules)


def garble(text: str) -> str:
    return text.encode("utf-8").decode("cp1252")


@pytest.mark.parametrize("clean", ["Weighted 1–5", "don’t", "Loading…", "a · b", "café", "× → ≥"])
def test_garbled_text_is_caught_and_clean_text_is_not(clean):
    assert rules.MOJIBAKE.search(garble(clean))
    assert not rules.MOJIBAKE.search(clean)


def test_ordinary_question_marks_and_ascii_pass():
    assert not rules.MOJIBAKE.search("Loading your organizations? Still here?")


def test_tracked_files_hold_no_mojibake():
    assert rules.mojibake_hits(str(REPO)) == []

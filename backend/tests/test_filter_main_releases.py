"""The host must filter releases before an older beta-capable backend claims."""

import json
from pathlib import Path
import subprocess
import sys

import pytest


HELPER = Path(__file__).resolve().parents[2] / "scripts" / "select-main-release.py"
MAIN = "v0.5.0-main.2.bbbbbbbbbbbb"


def release(tag=MAIN, **changes):
    return {
        "tag_name": tag, "draft": False, "prerelease": False,
        "published_at": "2026-10-10T10:00:00Z", "body": "Main notes",
        **changes,
    }


def run(raw):
    return subprocess.run(
        [sys.executable, str(HELPER)], input=raw, text=True,
        capture_output=True, check=False,
    )


def test_selector_chooses_newest_publication_and_excludes_beta():
    newer = release(published_at="2026-10-12T10:00:00Z")
    older = release("v0.5.0-main.1.aaaaaaaaaaaa")
    beta = release("v0.5.1-beta.3.cccccccccccc", published_at="2026-10-13T10:00:00Z")
    result = run(json.dumps([beta, newer, older]))
    assert result.returncode == 0 and not result.stderr
    assert result.stdout.strip() == MAIN[1:]


@pytest.mark.parametrize("changes", [
    {"tag_name": "v0.5.1-beta.3.cccccccccccc"}, {"draft": True},
    {"prerelease": True}, {"prerelease": "false"}, {"draft": 0},
    {"tag_name": MAIN + "\n"}, {"tag_name": MAIN[1:]},
    {"tag_name": "v0.5.0-main.2.bbbbbbb"},
])
def test_filter_refuses_other_tags_and_unfinished_releases(changes):
    result = run(json.dumps([release(**changes)]))
    assert result.returncode == 1 and not result.stdout
    assert "No published, non-prerelease main release" in result.stderr
    assert "Traceback" not in result.stderr


@pytest.mark.parametrize("raw", ["not json", "{}", "[]", "null", "[null, false, 3]"])
def test_filter_errors_are_clean_and_cannot_claim_an_update(raw):
    result = run(raw)
    assert result.returncode == 1 and not result.stdout
    assert "Release check failed:" in result.stderr and "Traceback" not in result.stderr


def test_filter_refuses_an_oversized_response():
    result = run(" " * 2_000_001)
    assert result.returncode == 1 and "size limit" in result.stderr

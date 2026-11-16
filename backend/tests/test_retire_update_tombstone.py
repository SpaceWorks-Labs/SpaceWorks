"""Upgrading removes the deleted update app without reviving other tombstones."""
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
BASH = shutil.which("bash")
pytestmark = pytest.mark.skipif(not BASH, reason="requires bash")


def invoke(tmp_path, value):
    return subprocess.run([BASH, "-c", '''
set -euo pipefail
source "$REPOSITORY_HELPER"
source "$TOMBSTONE_HELPER"
retire_update_tombstone
printf '%s' "$TOMBSTONED_APPS"
'''], env={**os.environ, "ROOT": tmp_path.as_posix(), "TOMBSTONED_APPS": value,
           "REPOSITORY_HELPER": (ROOT / "scripts/spaceworks-repository.sh").as_posix(),
           "TOMBSTONE_HELPER": (ROOT / "scripts/retire-update-tombstone.sh").as_posix()},
                          capture_output=True, text=True, timeout=30)


@pytest.mark.parametrize("value,expected", [
    ("updates", ""), ("events,updates,payments_rail", "events,payments_rail"),
    ("updates,bookings,updates", "bookings"), ("events, updates , bookings", "events, bookings"),
    ("events,devices", "events,devices"), ("update_custom,updates", "update_custom"),
])
def test_exported_tombstones_only_lose_updates(tmp_path, value, expected):
    result = invoke(tmp_path, value)
    assert result.returncode == 0, result.stderr
    assert result.stdout == expected


def test_private_env_rewrite_keeps_other_settings_and_tombstones(tmp_path):
    env = tmp_path / ".env"
    env.write_text("PRIVATE=retain\nTOMBSTONED_APPS='events,updates,presence'\nOTHER=value\n")
    result = invoke(tmp_path, "bookings,updates")
    assert result.returncode == 0, result.stderr
    assert result.stdout == "bookings"
    assert env.read_text() == "PRIVATE=retain\nOTHER=value\n\nTOMBSTONED_APPS=events,presence\n"

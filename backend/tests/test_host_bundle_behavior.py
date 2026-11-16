"""A staged upgrade replaces runtime files while preserving private install state."""
import os
import shutil
import subprocess
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
BASH = shutil.which("bash")
pytestmark = pytest.mark.skipif(not BASH, reason="requires bash")


def invoke(target, source):
    helper = ROOT / "scripts/install-host-bundle.sh"
    return subprocess.run([BASH, "-c", '''
set -euo pipefail
say() { printf '%s\n' "$*"; }
die() { printf '%s\n' "$*" >&2; exit 1; }
source "$HELPER"
install_staged_host_bundle "$SOURCE"
'''], env={**os.environ, "ROOT": target.as_posix(), "SOURCE": source.as_posix(),
           "HELPER": helper.as_posix()}, capture_output=True, text=True, timeout=30)


def test_staged_bundle_preserves_private_state_and_keeps_old_runtime_files(tmp_path):
    source = tmp_path / "release-fixture"
    manifest = (ROOT / "scripts/install-host-bundle.sh").read_text()
    files = re.search(r"HOST_BUNDLE_FILES=\((.*?)\n  \)", manifest, re.S)[1].split()
    for name in files:
        path = source / name
        path.parent.mkdir(parents=True, exist_ok=True)
        if name == "deploy/contracts/programmes.json" and not (ROOT / name).exists():
            path.write_text('{"schema_version":1,"installer_test_fixture":true}\n')
        else:
            shutil.copy(ROOT / name, path)
    target = tmp_path / "installed"
    target.mkdir()
    (target / "scripts").mkdir()
    (target / "scripts/update.sh").write_text("old updater")
    (target / "scripts/install-auto-update.sh").write_text("old polling")
    (target / ".env").write_text("PRIVATE=retained\n")
    (target / ".spaceworks-version").write_text("previous release\n")
    result = invoke(target, source)
    assert result.returncode == 0, result.stderr
    assert (target / "scripts/update.sh").read_bytes() == (ROOT / "scripts/update.sh").read_bytes()
    assert (target / "scripts/install-runner.sh").exists()
    assert (target / ".env").read_text() == "PRIVATE=retained\n"
    assert (target / ".spaceworks-version").read_text() == "previous release\n"
    backup = next((target / "backups").glob("host-config-*"))
    assert (backup / "scripts/update.sh").read_text() == "old updater"
    assert (backup / "scripts/install-auto-update.sh").read_text() == "old polling"
    assert not (target / "scripts/install-auto-update.sh").exists()


def test_incomplete_bundle_refuses_before_replacing_any_file(tmp_path):
    target, source = tmp_path / "installed", tmp_path / "incomplete"
    target.mkdir()
    source.mkdir()
    (target / "setup.sh").write_text("private original")
    result = invoke(target, source)
    assert result.returncode != 0 and "lacks VERSION" in result.stderr
    assert (target / "setup.sh").read_text() == "private original"
    assert not (target / "backups").exists()

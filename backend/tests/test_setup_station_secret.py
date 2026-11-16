"""Exercise secret creation/preservation without the questionnaire or Docker."""
import base64
import os
from pathlib import Path
import re
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[2]
BASH = shutil.which("bash")
pytestmark = pytest.mark.skipif(not BASH, reason="requires Bash")


def run_setup(directory):
    script = r"""set -euo pipefail
ROOT="$TEST_REPO_ROOT"
source "$ROOT/scripts/setup-question-input.sh"
source "$ROOT/scripts/setup-write-environment.sh"
configure_release_repository() { :; }
say() { :; }
die() { echo "$*" >&2; exit 1; }
ANSWERS_CONFIRMED=yes
HTTPS_MODE=1; WEBHOST=localhost; HOSTING_MODEL=1; SITE_ORIGINS=''
RUN_FRONTEND=1; STORAGE=1; SPACEWORKS_EDITION=events
SPACEWORKS_REPOSITORY=SpaceWorks-Labs/SpaceWorks
MAKERSPACE_BACKEND_IMAGE=example/backend; MAKERSPACE_FRONTEND_IMAGE=example/frontend
PUBLIC_DOMAIN=''; TLS_EMAIL=''
# The layer selector is an install-local file, while helper sources remain real.
HELPER_ROOT="$ROOT"
ROOT="$PWD"
if [[ ! -f .env ]]; then write_setup_environment; fi
ROOT="$HELPER_ROOT"
source "$ROOT/scripts/setup-first-run.sh"
"""
    return subprocess.run(
        [BASH, "-c", script], cwd=directory,
        env={**os.environ, "TEST_REPO_ROOT": ROOT.as_posix()},
        text=True, capture_output=True, timeout=30,
    )


def test_fresh_setup_generates_independent_secret_and_rerun_preserves_it(tmp_path):
    first = run_setup(tmp_path)
    assert first.returncode == 0, first.stderr
    original = (tmp_path / ".env").read_bytes()
    pepper = re.search(rb"^EVENT_STATION_PIN_PEPPER='([A-Za-z0-9]{50})'$", original, re.M)
    assert pepper, "station PINs require an independent random secret of at least 32 bytes"
    assert pepper[1] not in re.search(rb"^SECRET_KEY='([^']+)'$", original, re.M)[1]
    assert pepper[1].decode() not in first.stdout + first.stderr
    master = re.search(rb"^PII_MASTER_KEY='([^']+)'$", original, re.M)[1]
    search = re.search(rb"^PII_SEARCH_HASH_KEY='([^']+)'$", original, re.M)[1]
    assert len(base64.urlsafe_b64decode(master)) == len(base64.urlsafe_b64decode(search)) == 32
    assert master != search
    second = run_setup(tmp_path)
    assert second.returncode == 0, second.stderr
    assert (tmp_path / ".env").read_bytes() == original
    if os.name != "nt":
        assert (tmp_path / ".env").stat().st_mode & 0o777 == 0o600


def test_existing_install_keeps_operator_provided_station_secret(tmp_path):
    existing = b"EVENT_STATION_PIN_PEPPER='operator-owned-station-secret-at-least-32-bytes'\n"
    (tmp_path / ".env").write_bytes(existing)
    result = run_setup(tmp_path)
    assert result.returncode == 0, result.stderr
    assert (tmp_path / ".env").read_bytes() == existing

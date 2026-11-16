"""Legacy restore must refuse a sibling before any control or storage effect."""
import os
from pathlib import Path
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[2]
BASH = shutil.which("bash")
pytestmark = pytest.mark.skipif(not BASH, reason="requires bash")
IDENTITY = "makerspace_manager|16384|aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"


@pytest.mark.parametrize("active", [
    "sibling|16385|bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
    "makerspace_manager|16385|aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
    "makerspace_manager|16384|bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
    "", "invalid/name|1|aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
])
def test_different_or_unproven_active_database_is_refused(active):
    result = prove(active)
    assert result.returncode != 0
    assert "restore refused" in result.stderr
    assert "PROVEN=" not in result.stdout


def prove(active=IDENTITY):
    return subprocess.run([BASH, "-c", '''set -euo pipefail
die() { echo "$*" >&2; exit 1; }
compose() {
  if [[ "$1" == run ]]; then printf '%s\n' "$ACTIVE";
  else printf '%s\n' "$BOOTSTRAP"; fi
}
COMPOSE=(compose)
source "$RESTORE_SCRIPT_DIR/restore-database-identity.sh"
prove_restore_database
printf 'PROVEN=%s\n' "$RESTORE_DATABASE"
'''], env={**os.environ, "ACTIVE": active, "BOOTSTRAP": IDENTITY,
          "RESTORE_SCRIPT_DIR": (ROOT / "scripts").as_posix()},
        text=True, capture_output=True, timeout=10)


def test_matching_queried_identity_supplies_explicit_restore_database():
    result = prove()
    assert result.returncode == 0, result.stderr
    assert result.stdout == "PROVEN=makerspace_manager\n"


def test_restore_proves_identity_before_any_control_and_never_targets_postgres_default():
    source = (ROOT / "scripts/restore.sh").read_text()
    assert source.index("prove_restore_database") < source.index('WORK="$OPS_WORK_DIR/')
    assert '"$POSTGRES_DB"' not in source
    assert 'local database_name="${1:-$RESTORE_DATABASE}"' in source
    ops = (ROOT / "scripts/restore-database-ops.sh").read_text()
    assert '"$POSTGRES_DB"' not in ops
    for line in (source + ops).splitlines():
        if "pg_restore" in line or "pg_dump" in line:
            assert '"$SPACEWORKS_RESTORE_DATABASE"' in line or '"$temp_db"' in line

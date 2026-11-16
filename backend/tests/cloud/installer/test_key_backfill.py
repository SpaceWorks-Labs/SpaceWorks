"""Legacy key generation requires unused-state proof; configured keys never rotate."""
import base64
import os
from pathlib import Path
import re
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[4]
BASH = shutil.which("bash")
pytestmark = pytest.mark.skipif(not BASH, reason="requires Bash")


def run(root, proof="1|1"):
    return subprocess.run([BASH, "-c", '''set -euo pipefail
die() { echo "$*" >&2; exit 1; }
compose() { printf '%s\n' "$PROOF"; }
COMPOSE=(compose)
source "$REPO/scripts/compose-deployment.sh"
source "$REPO/scripts/setup-question-input.sh"
source "$REPO/scripts/setup-write-environment.sh"
source "$REPO/scripts/installer/key-backfill.sh"
plan_key_backfill
apply_key_backfill
'''], env={**os.environ, "ROOT": root.as_posix(), "REPO": ROOT.as_posix(), "PROOF": proof},
        cwd=root, capture_output=True, text=True, timeout=15)


def test_unused_keys_are_independent_and_seeded_once(tmp_path):
    (tmp_path / ".env").write_text("SECRET_KEY=existing\n")
    first = run(tmp_path)
    assert first.returncode == 0, first.stderr
    original = (tmp_path / ".env").read_bytes()
    master = re.search(rb"^PII_MASTER_KEY='([^']+)'$", original, re.M)[1]
    search = re.search(rb"^PII_SEARCH_HASH_KEY='([^']+)'$", original, re.M)[1]
    assert len(base64.urlsafe_b64decode(master)) == len(base64.urlsafe_b64decode(search)) == 32
    assert master != search and master.decode() not in first.stdout + first.stderr
    second = run(tmp_path, "invalid-unused-proof-not-needed-for-configured-keys")
    assert second.returncode == 0 and (tmp_path / ".env").read_bytes() == original


@pytest.mark.parametrize("proof", ["0|1", "1|0", "0|0", "invalid"])
def test_existing_key_use_or_unknown_proof_cannot_create_replacement_material(tmp_path, proof):
    original = b"SECRET_KEY=existing\nPII_MASTER_KEY=\nPII_SEARCH_HASH_KEY=\n"
    (tmp_path / ".env").write_bytes(original)
    result = run(tmp_path, proof)
    assert result.returncode != 0 and (tmp_path / ".env").read_bytes() == original


def test_aws_broker_does_not_generate_an_unused_local_master(tmp_path):
    (tmp_path / ".env").write_text("PII_KEY_BROKER=aws_kms\n")
    result = run(tmp_path)
    assert result.returncode == 0, result.stderr
    data = (tmp_path / ".env").read_text()
    assert "PII_MASTER_KEY=" not in data and "PII_SEARCH_HASH_KEY=" in data


def test_invalid_existing_key_refuses_before_changes_without_echoing_value(tmp_path):
    original = b"PII_MASTER_KEY=invalid-key-do-not-echo\n"
    (tmp_path / ".env").write_bytes(original)
    result = run(tmp_path)
    assert result.returncode != 0 and (tmp_path / ".env").read_bytes() == original
    assert "invalid-key-do-not-echo" not in result.stdout + result.stderr

"""Image rollback retains forward schema; retired automatic restore plans stay gone."""
import os
from pathlib import Path
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[2]
BASH = shutil.which("bash")
OLD = "0.9.2-main.1.aaaaaaaaaaaa"
pytestmark = pytest.mark.skipif(not BASH, reason="requires Bash")


def rollback(tmp_path, *, proof=True, readiness=True, tag=OLD):
    log = tmp_path / "commands"
    result = subprocess.run([BASH, "-c", '''set -euo pipefail
say() { printf '%s\n' "$*"; }
warn() { printf '%s\n' "$*" >&2; }
compose() { printf '%s\n' "$*" >> "$LOG"; }
install_producer_capability() { printf 'producer\n' >> "$LOG"; [[ "$PROOF" == 1 ]]; }
refresh_update_proxy_edges() { printf 'edges\n' >> "$LOG"; }
wait_for_backend() { [[ "$READY" == 1 ]]; }
cleanup_run_once_jobs() { printf 'cleanup\n' >> "$LOG"; }
COMPOSE=(compose)
APP_SERVICE=backend
WORKER_SERVICES=(worker beat live)
IMAGE_SERVICES=(orchestration-init migrate orchestration-ready backend live worker beat frontend)
ROLLBACK_SERVICES=(backend live worker beat frontend)
VERSION_FILE="$ROOT/.spaceworks-version"
backup_name=pre-update-fixture.sql.gz
MAKERSPACE_BACKEND_IMAGE=example/backend
source "$HELPER"
rollback_application_images
'''], env={**os.environ, "ROOT": tmp_path.as_posix(), "LOG": log.as_posix(),
            "HELPER": (ROOT / "scripts/update-rollback.sh").as_posix(), "previous_version": tag,
            "PROOF": "1" if proof else "0", "READY": "1" if readiness else "0"},
        capture_output=True, text=True, timeout=10)
    return result, log.read_text() if log.exists() else ""


def test_completed_image_rollback_restarts_without_migrations_or_database_restore(tmp_path):
    result, log = rollback(tmp_path)
    assert result.returncode == 0, result.stderr
    assert "up -d --no-deps backend live worker beat frontend" in log
    assert log.index("producer") < log.index("up -d")
    assert "Database changes remain" in result.stdout
    assert "pg_restore" not in log and "backup_control" not in log and "update_control" not in log
    assert (tmp_path / ".spaceworks-version").read_text().strip() == OLD


def test_missing_producer_proof_keeps_writers_stopped_and_version_unchanged(tmp_path):
    marker = tmp_path / ".spaceworks-version"
    marker.write_text("prior-marker\n")
    result, log = rollback(tmp_path, proof=False)
    assert result.returncode == 1
    assert "stop backend worker beat live" in log and "up -d" not in log
    assert marker.read_text() == "prior-marker\n"


def test_failed_readiness_never_records_successful_rollback_version(tmp_path):
    result, log = rollback(tmp_path, readiness=False)
    assert "automatic rollback" in result.stdout
    assert not (tmp_path / ".spaceworks-version").exists()
    assert "cleanup" not in log


@pytest.mark.parametrize("tag", ["0.9.2-beta.1.aaaaaaaaaaaa", "latest", "0.9.2-main.1.bad", ""])
def test_unproven_previous_tag_cannot_start_any_service(tmp_path, tag):
    result, log = rollback(tmp_path, tag=tag)
    assert result.returncode == 0 and not log
    assert not (tmp_path / ".spaceworks-version").exists()

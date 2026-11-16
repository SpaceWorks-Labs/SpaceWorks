"""Disaster restore into an outside database (decision 239): host-script structure and behaviour.

Host-only like the neighbouring restore tests: they read scripts outside the backend build context.
The container calls are replaced by a recording shell function, so no Docker or database is touched.
"""
import os
from pathlib import Path
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[2]
BASH = shutil.which("bash")
pytestmark = pytest.mark.skipif(not BASH, reason="requires bash")
IDENTITY = "makerspace_manager|16384|aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
OWNER_URL = "postgres://postgres.abcd:p\\'ss@aws-0-eu.pooler.supabase.com:5432/postgres?sslmode=require"

PRELUDE = r"""set -uo pipefail
die() { echo "$*" >&2; exit 1; }
deployment_value() {
  case "$1" in
    SPACEWORKS_DATABASE) printf '%s' "${DB_MODE-external}" ;;
    SPACEWORKS_MAINTENANCE_DATABASE_URL) printf '%s' "${MAINT-}" ;;
    DATABASE_MAINTENANCE_CONNECTION_MODE) printf '%s' "${MAINT_MODE-}" ;;
    DATABASE_CONNECTION_MODE) printf '%s' "${CONN_MODE-}" ;;
  esac
}
compose() {
  printf 'ARGS:%s\n' "$*" >> "$LOG"
  printf 'ENV:%s|%s\n' "${DATABASE_URL-unset}" "${DATABASE_CONNECTION_MODE-unset}" >> "$LOG"
  case "$*" in
    *has-data*) printf '%s\n' "${ACCOUNTS-3}" ;;
    *" identity"*) if [[ "$*" == *DATABASE_URL* ]]; then printf '%s\n' "${OWNER_ID-}"; else printf '%s\n' "${ACTIVE_ID-}"; fi ;;
  esac
}
COMPOSE=(compose)
RESTORE_ID=11111111-2222-3333-4444-555555555555
RESTORE_SCRIPT_DIR="$SCRIPTS"
source "$SCRIPTS/restore-database-ops.sh"
source "$SCRIPTS/restore-database-identity.sh"
"""


def run(body, tmp_path, **env):
    log = tmp_path / "calls.log"
    log.write_text("")
    result = subprocess.run(
        [BASH, "-c", PRELUDE + body],
        env={**os.environ, "SCRIPTS": (ROOT / "scripts").as_posix(), "LOG": log.as_posix(),
             "ACTIVE_ID": IDENTITY, "OWNER_ID": IDENTITY, "MAINT": OWNER_URL, **env},
        text=True, capture_output=True, timeout=20)
    return result, log.read_text()


def test_identity_proof_compares_runtime_pointer_with_the_owner_login(tmp_path):
    result, log = run('prove_restore_database; printf "DB=%s\\n" "$RESTORE_DATABASE"', tmp_path)
    assert result.returncode == 0, result.stderr
    assert "DB=makerspace_manager" in result.stdout
    assert log.count("ARGS:") == 2


@pytest.mark.parametrize("owner", [
    "other|16384|aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
    "makerspace_manager|16385|aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
    "",
])
def test_pointer_that_differs_from_the_owner_database_is_refused(tmp_path, owner):
    result, _ = run("prove_restore_database", tmp_path, OWNER_ID=owner)
    assert result.returncode != 0 and "restore refused" in result.stderr


def test_owner_url_reaches_the_container_through_the_environment_never_argv(tmp_path):
    result, log = run("external_step dump /var/lib/spaceworks/ops/work/x/pre.dump", tmp_path, CONN_MODE="session")
    assert result.returncode == 0, result.stderr
    args = [line for line in log.splitlines() if line.startswith("ARGS:")][0]
    assert "pooler.supabase.com" not in args and "p'ss" not in args
    assert "-e DATABASE_URL -e DATABASE_CONNECTION_MODE" in args and "--role management" in args
    # env_setting() escaping is undone, and the declared connection mode is passed through.
    assert "ENV:postgres://postgres.abcd:p'ss@aws-0-eu.pooler.supabase.com:5432/postgres?sslmode=require|session" in log


def test_maintenance_connection_mode_wins_and_direct_is_the_default(tmp_path):
    _, log = run("external_step identity", tmp_path, MAINT_MODE="session", CONN_MODE="direct")
    assert "|session\n" in log
    _, log = run("external_step identity", tmp_path)
    assert "|direct\n" in log


def test_missing_owner_url_refuses_before_any_container_call(tmp_path):
    result, log = run("external_step identity", tmp_path, MAINT="")
    assert result.returncode != 0 and "SPACEWORKS_MAINTENANCE_DATABASE_URL" in result.stderr
    assert log == ""


def test_populated_outside_database_needs_explicit_replace(tmp_path):
    result, _ = run("RESTORE_DATABASE=makerspace_manager; confirm_external_replace", tmp_path)
    assert result.returncode != 0 and "--replace" in result.stderr
    ok, _ = run("RESTORE_DATABASE=makerspace_manager; REPLACE_CONFIRMED=1; confirm_external_replace", tmp_path)
    assert ok.returncode == 0, ok.stderr


def test_empty_outside_database_and_bundled_database_need_no_confirmation(tmp_path):
    empty, _ = run("RESTORE_DATABASE=m; confirm_external_replace", tmp_path, ACCOUNTS="0")
    assert empty.returncode == 0, empty.stderr
    bundled, log = run("RESTORE_DATABASE=m; confirm_external_replace", tmp_path, DB_MODE="bundled")
    assert bundled.returncode == 0 and log == ""


def test_grant_proof_for_a_scratch_database_names_it_and_returns_oid_and_uuid(tmp_path):
    body = "RESTORE_DATABASE=makerspace_manager; restore_db_grant_proof spaceworks_restore_abc"
    result, log = run(body, tmp_path)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "16384|aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    assert "identity spaceworks_restore_abc" in log


def test_external_snapshot_replace_and_rollback_use_container_paths(tmp_path):
    result, log = run("PRE_DB=/x; BUNDLE=/y; restore_db_snapshot; restore_db_replace; restore_db_rollback", tmp_path)
    assert result.returncode == 0, result.stderr
    base = "/var/lib/spaceworks/ops/work/restore-11111111-2222-3333-4444-555555555555"
    assert f"dump {base}/pre-restore.dump" in log
    assert f"restore {base}/bundle/database.dump" in log
    assert f"restore {base}/pre-restore.dump" in log
    assert " db " not in log  # no bundled `db` container is touched


def test_restore_script_routes_every_database_step_through_the_ops_file():
    source = (ROOT / "scripts/restore.sh").read_text()
    for name in ("restore_db_snapshot", "restore_db_replace", "restore_db_rollback",
                 "restore_db_scratch_load", "restore_db_scratch_drop", "restore_db_grant_proof",
                 "confirm_external_replace"):
        assert name in source
    assert " db sh -c" not in source and "pg_restore" not in source and "pg_dump" not in source
    assert "--replace" in source and "SPACEWORKS_RESTORE_REPLACE" in source
    assert source.index("confirm_external_replace") < source.index('WORK="$OPS_WORK_DIR/')


def test_external_helper_only_accepts_fixed_steps_and_scratch_names():
    helper = (ROOT / "scripts/installer/external-restore-db.py").read_text()
    assert 'startswith("spaceworks_restore_")' in helper and "WORK = " in helper
    assert "client_binary" not in helper  # version choice stays inside apps.backup.postgres_client
    assert "run_client(" in helper and "configuration_spec(" in helper


def test_new_scripts_are_in_the_privileged_inventory_and_the_host_bundle():
    inventory = (ROOT / "backend/apps/backup/privileged_script_inventory.py").read_text()
    bundle = (ROOT / "scripts/install-host-bundle.sh").read_text()
    for name in ("installer/external-restore-db.py", "installer/frontend-choice.sh", "restore-database-ops.sh"):
        assert f"'{name}'" in inventory and f"scripts/{name}" in bundle


def test_installer_menu_offers_outside_services_and_keeps_cancel_as_the_default():
    entry = (ROOT / "scripts/installer/install-entry.sh").read_text()
    runtime = (ROOT / "scripts/installer/install-runtime.sh").read_text()
    for text in (entry, runtime):
        assert "7) Change outside services (database, Redis, storage, email)" in text
        assert "Choose 1-7 [4]" in text
    assert "scripts/switch-services.sh menu" in entry and "ACTION=services" in runtime
    assert "INSTALL_MENU_CHOICE:-4}" in entry and "ACTION:-4}" in runtime

"""Secret continuity, resumable install identity and fail-closed shell seams."""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

import pytest

ROOT = Path(__file__).resolve().parents[4]
BASH = shutil.which("bash")
VERSION = "0.9.2-main.2.bbbbbbbbbbbb"
REPOSITORY = "SpaceWorks-Labs/SpaceWorks"


def script(name):
    spec = importlib.util.spec_from_file_location("installer_test", ROOT / "scripts/installer" / name)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def state(root, action, *options):
    return subprocess.run([sys.executable, str(ROOT / "scripts/installer/state.py"), action, "--root", str(root),
                           "--repository", REPOSITORY, "--release", VERSION, *options],
                          capture_output=True, text=True, timeout=15)


def installation(root):
    (root / "setup.sh").write_text("#!/bin/bash\necho selected\n")
    (root / ".spaceworks-release.json").write_text(json.dumps({"schema_version": 1, "repository": REPOSITORY, "release": VERSION,
        "commit": "b" * 40, "archive_sha256": "c" * 64}))
    (root / ".spaceworks-answers").write_text("ADMINPASS=private-test-password\n")
    (root / ".spaceworks-answers").chmod(0o600)


def test_resume_binds_files_owner_release_and_exact_private_settings(tmp_path):
    installation(tmp_path)
    assert state(tmp_path, "create").returncode == 0
    assert state(tmp_path, "validate").returncode == 0
    (tmp_path / ".env").write_text("SECRET_KEY=private-key\n")
    (tmp_path / ".env").chmod(0o600)
    assert state(tmp_path, "phase", "--phase", "environment").returncode == 0
    marker = json.loads((tmp_path / ".spaceworks-install.json").read_text())
    assert marker["commit"] == "b" * 40 and marker["archive_sha256"] == "c" * 64
    assert "private-test-password" not in json.dumps(marker)
    (tmp_path / ".env").write_text("SECRET_KEY=replaced\n")
    result = state(tmp_path, "validate")
    assert result.returncode == 1 and "replaced" not in result.stderr


def test_resume_refuses_modified_release_without_overwriting_it(tmp_path):
    installation(tmp_path)
    assert state(tmp_path, "create").returncode == 0
    (tmp_path / "setup.sh").write_text("modified operator file")
    assert state(tmp_path, "validate").returncode == 1
    assert (tmp_path / "setup.sh").read_text() == "modified operator file"


def test_interrupted_copy_recovers_original_answers_before_environment_creation(tmp_path):
    source, target = tmp_path / "source", tmp_path / "target"
    source.mkdir(); target.mkdir()
    installation(source)
    assert state(target, "prepare", "--source", str(source)).returncode == 0
    assert state(target, "validate").returncode == 0
    assert state(target, "restore-answers").returncode == 0
    assert (target / ".spaceworks-answers").read_bytes() == (source / ".spaceworks-answers").read_bytes()
    assert not (target / ".env").exists()
    (target / "setup.sh").write_text("unrelated partial file")
    assert state(target, "validate").returncode == 1
    assert (target / "setup.sh").read_text() == "unrelated partial file"


def test_retention_protects_current_ambiguous_and_symlinked_material(tmp_path):
    module = script("retention.py")
    backups = tmp_path / "backups"
    backups.mkdir()
    current = backups / "pre-update-20260101T000000Z-1.sql.gz"
    current.write_text("current")
    os.utime(current, (1, 1))
    result = subprocess.run([sys.executable, str(ROOT / "scripts/installer/retention.py"), "--root", str(tmp_path),
                             "--exclude", str(current)], capture_output=True, timeout=10)
    assert result.returncode == 0 and current.exists()
    (tmp_path / ".spaceworks-import-pending.json").write_text("ambiguous")
    result = subprocess.run([sys.executable, str(ROOT / "scripts/installer/retention.py"), "--root", str(tmp_path)],
                            capture_output=True, timeout=10)
    assert result.returncode == 0 and current.exists()
    if hasattr(os, "symlink") and os.name != "nt":
        link = backups / "host-config-20260101T000000Z-1"
        link.symlink_to(tmp_path)
        module.remove_owned(link, link.lstat().st_uid, time.time())
        assert link.is_symlink() and current.exists()


@pytest.mark.skipif(not hasattr(os, "geteuid") or getattr(os, "geteuid", lambda: -1)() != 0, reason="record metadata transport runs as root")
def test_record_snapshot_restores_exact_bytes_mode_ownership_and_extra_records(tmp_path, monkeypatch):
    module = script("record-snapshot.py")
    ops = tmp_path / "ops"
    ops.mkdir()
    record = ops / "compose-topology.json"
    record.write_bytes(b'{"original":true}\n')
    record.chmod(0o640)
    snapshot = tmp_path / "snapshot.json"
    original = record.stat()
    monkeypatch.setattr(sys, "argv", ["record-snapshot.py", "snapshot", str(ops), str(snapshot)])
    module.main()
    record.write_text("changed")
    record.chmod(0o600)
    (ops / "compose-topology-tls.json").write_text("extra")
    monkeypatch.setattr(sys, "argv", ["record-snapshot.py", "restore", str(ops), str(snapshot)])
    module.main()
    assert record.read_bytes() == b'{"original":true}\n'
    assert record.stat().st_mode == original.st_mode and record.stat().st_uid == original.st_uid
    assert record.stat().st_gid == original.st_gid and record.stat().st_mtime_ns == original.st_mtime_ns
    assert not (ops / "compose-topology-tls.json").exists()


@pytest.mark.skipif(not BASH, reason="requires Bash")
@pytest.mark.parametrize("ambient,saved,success", [("", "/custom/ops", True), ("/other/ops", "/custom/ops", False)])
def test_saved_state_paths_cannot_be_redirected_by_ambient_environment(tmp_path, ambient, saved, success):
    (tmp_path / ".env").write_text(f"SPACEWORKS_OPS_HOST_DIR='{saved}'\nSPACEWORKS_HOST_STATE_DIR='/custom/host'\n")
    result = subprocess.run([BASH, "-c", 'source "$HELPER"; resolve_host_paths; result=$?; [[ "$result" == 0 ]] || exit "$result"; printf "%s" "$OPS_DIR"'],
        env={**os.environ, "HELPER": (ROOT / "scripts/installer/host-paths.sh").as_posix(), "ROOT": tmp_path.as_posix(),
             "SPACEWORKS_OPS_HOST_DIR": ambient, "SPACEWORKS_HOST_STATE_DIR": ""}, capture_output=True, text=True, timeout=10)
    assert (result.returncode == 0) is success
    if success:
        assert result.stdout == saved


@pytest.mark.skipif(not BASH, reason="requires Bash")
def test_storage_proxy_has_large_part_limit_and_api_limit_stays_separate(tmp_path):
    result = subprocess.run([BASH, "-c", 'source "$HELPER"; write_proxy_nginx_config'],
        env={**os.environ, "HELPER": (ROOT / "scripts/setup-proxy-config.sh").as_posix(),
             "ROOT": tmp_path.as_posix(), "WEBHOST": "tools.example.org", "STORAGE": "1"},
        capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
    api, storage = (tmp_path / "spaceworks-proxy.nginx.conf").read_text().split("server_name files.", 1)
    assert "client_max_body_size 128m;" in api
    assert "proxy_set_header Host $http_host;" in api and "proxy_set_header Host $host;" not in api
    assert "client_max_body_size 20481m;" in storage and "128m" not in storage
    assert "proxy_request_buffering off;" in storage
    assert "proxy_http_version 1.1;" in storage
    assert "proxy_send_timeout 3600s;" in storage and "proxy_read_timeout 3600s;" in storage


def test_all_restore_sql_paths_fail_fast_and_never_restore_ownership():
    source = (ROOT / "scripts/restore.sh").read_text()
    commands = [line for line in source.splitlines() if "pg_restore " in line]
    assert len(commands) == 4
    assert all("--exit-on-error" in line and "--no-owner" in line and "--no-acl" in line for line in commands)


def test_import_preflight_precedes_environment_and_has_management_role():
    source = (ROOT / "scripts/import-backup.sh").read_text()
    assert "--role management python manage.py preflight_backup_import" in source
    assert source.index("manage.py preflight_backup_import") < source.index("install_import_environment ||")
    helper = (ROOT / "scripts/installer/import-environment.sh").read_text()
    assert helper.index("refresh_compose_config ||") < helper.index("--force-recreate")
    assert "WORKER_SERVICES" in helper and "{{.Image}}" in helper


@pytest.mark.skipif(os.name == "nt", reason="requires POSIX fsync/ownership")
def test_import_journal_refuses_environment_only_rollback_after_restore_registration(tmp_path):
    ops = tmp_path / "ops"
    work = ops / "work/import-abc123"
    work.mkdir(parents=True)
    (work / "records.json").write_text("{}")
    backup = ".env.pre-restore-20261018T120000Z-123"
    (tmp_path / backup).write_text("SECRET_KEY=previous\n")
    command = [sys.executable, str(ROOT / "scripts/installer/import-journal.py")]

    def invoke(action, *extra):
        return subprocess.run([*command, action, str(tmp_path), str(ops), *extra],
                              capture_output=True, timeout=10)

    assert invoke("begin", str(work), backup, "sha256:" + "a" * 64).returncode == 0
    assert invoke("read").returncode == 0
    assert invoke("seal").returncode == 0
    result = invoke("read")
    assert result.returncode == 1 and b"Environment-only rollback is refused" in result.stderr
    restore_id = "11111111-2222-3333-4444-555555555555"
    assert invoke("registered", restore_id).returncode == 0
    assert restore_id.encode() in invoke("read").stderr
    assert (tmp_path / backup).read_text() == "SECRET_KEY=previous\n"


@pytest.mark.skipif(not BASH, reason="requires Bash")
def test_ambiguous_import_stops_writers_and_retains_environment(tmp_path):
    (tmp_path / ".env").write_text("SECRET_KEY=imported\n")
    result = subprocess.run([BASH, "-c", '''set -euo pipefail
source "$HELPER"
compose() { printf '%s\n' "$*" >> "$CALLS"; }
COMPOSE=(compose); APP_SERVICE=backend; WORKER_SERVICES=(live worker beat)
import_env_applied=1; import_env_ambiguous=1
rollback_import_environment
'''], env={**os.environ, "HELPER": (ROOT / "scripts/installer/import-environment.sh").as_posix(),
            "CALLS": (tmp_path / "calls").as_posix()}, capture_output=True, text=True, timeout=10)
    assert result.returncode == 1
    assert (tmp_path / "calls").read_text().strip() == "stop backend live worker beat"
    assert (tmp_path / ".env").read_text() == "SECRET_KEY=imported\n"


# test_full_installer_has_no_free_profile_mode was rewritten into
# tests/cloud/installer/test_free_profile_option.py (owner: offer free as an opt-in).


@pytest.mark.skipif(not BASH, reason="requires Bash")
def test_failed_compose_render_cannot_be_hidden_by_later_successful_help(tmp_path):
    result = subprocess.run([BASH, "-c", '''set -euo pipefail
docker() { [[ "$*" != *config* ]] || return 2; echo '--wait --no-deps --force-recreate --remove-orphans'; }
source "$HELPER"
probe_compose_capabilities || exit $?
echo should-not-complete
'''], env={**os.environ, "ROOT": ROOT.as_posix(),
            "HELPER": (ROOT / "scripts/installer/compose-capabilities.sh").as_posix()},
        capture_output=True, text=True, timeout=10)
    assert result.returncode == 2 and "should-not-complete" not in result.stdout


@pytest.mark.skipif(not BASH, reason="requires Bash")
def test_missing_station_pepper_is_backfilled_once_under_operation_lock(tmp_path):
    (tmp_path / ".env").write_text("SECRET_KEY=existing\n")
    command = '''set -euo pipefail
die() { echo "$*" >&2; exit 1; }
source "$REPO/scripts/setup-question-input.sh"
source "$REPO/scripts/compose-deployment.sh"
source "$REPO/scripts/installer/setup-state.sh"
SPACEWORKS_OPERATION_LOCK_HELD=1
ensure_station_pepper no-refresh
'''
    env = {**os.environ, "ROOT": tmp_path.as_posix(), "REPO": ROOT.as_posix()}
    first = subprocess.run([BASH, "-c", command], env=env, capture_output=True, text=True, timeout=10)
    assert first.returncode == 0, first.stderr
    original = (tmp_path / ".env").read_bytes()
    assert b"EVENT_STATION_PIN_PEPPER=" in original
    second = subprocess.run([BASH, "-c", command], env=env, capture_output=True, text=True, timeout=10)
    assert second.returncode == 0 and (tmp_path / ".env").read_bytes() == original


@pytest.mark.skipif(not BASH, reason="requires Bash")
def test_unsupported_legacy_layout_refuses_before_provider_backup_or_environment_changes(tmp_path):
    (tmp_path / ".spaceworks-version").write_text(VERSION)
    (tmp_path / ".spaceworks-layer").write_text("tls")
    (tmp_path / ".env").write_text("SECRET_KEY=old\n")
    result = subprocess.run([BASH, "-c", '''set -euo pipefail
die() { echo "$*" >&2; exit 1; }
docker() { echo unexpected-docker; exit 99; }
python3() { echo unexpected-provider; exit 99; }
source "$HELPER"
transition_pre_h1
'''], env={**os.environ, "ROOT": tmp_path.as_posix(), "OPS_DIR": (tmp_path / "ops").as_posix(),
            "UPDATE_SCRIPT_DIR": (ROOT / "scripts").as_posix(), "HELPER": (ROOT / "scripts/installer/pre-h1.sh").as_posix()},
        capture_output=True, text=True, timeout=10)
    assert result.returncode == 1 and "Unsupported" in result.stderr
    assert "unexpected-" not in result.stdout
    assert (tmp_path / ".env").read_text() == "SECRET_KEY=old\n"

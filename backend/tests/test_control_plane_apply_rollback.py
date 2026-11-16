"""Control-plane edits must restore settings and topology together on failure."""
import os
import subprocess

import pytest

from tests.test_control_plane_apply_settings import (
    BASH, ROOT, assert_no_refresh, installation, write_script,
)

pytestmark = pytest.mark.skipif(not BASH, reason="requires bash")
ORIGINAL = (b"# Installed settings\nSPACEWORKS_RUN_FRONTEND=yes\n"
            b"SECRET_KEY='keep me'\nCONTROL_PLANE_PROXY='false'\n"
            b"HTTP_PORT=8081\nCONTROL_PLANE_ALLOW_CIDRS='1.2.3.4'\n"
            b"CONTROL_PLANE_TUNNEL_PORT='9443'\n# Last setting\n")
TOGGLE = ["--control-plane", "on", "--allow-cidrs", "10.0.0.0/8 192.0.2.1"]


def run_toggle(installation, original=ORIGINAL, layer="none", args=TOGGLE, **changes):
    root, env = installation
    (root / ".env").write_bytes(original)
    (root / ".spaceworks-layer").write_text(layer + "\n", newline="\n")
    return subprocess.run([BASH, "scripts/apply-settings.sh", *args], cwd=root,
                          env={**env, **changes}, capture_output=True, text=True, timeout=15)


def record_refresh_and_compose(root):
    # A returning function exercises cleanup's rollback, including its error handling.
    write_script(root / "scripts/setup-host-orchestration.sh", '''
refresh_compose_config() {
  local count=1
  [[ ! -f "$ROOT/refresh-count" ]] || count=$(( $(cat "$ROOT/refresh-count") + 1 ))
  printf '%s\\n' "$count" > "$ROOT/refresh-count"
  cp "$ROOT/.env" "$ROOT/refresh-$count.env"
  [[ "$count" != 2 || "${TEST_ROLLBACK_REFRESH_FAIL:-0}" != 1 ]] || return 73
  return 0
}
''')
    write_script(root / "scripts/spaceworks-compose.sh", '''
printf '%s\\n' "$*" >> "$SPACEWORKS_UPDATE_INSTALL_DIR/compose.log"
[[ $(wc -l < "$SPACEWORKS_UPDATE_INSTALL_DIR/compose.log") -gt 1 ]] || exit 72
''')


@pytest.mark.parametrize("trailing_newline", [True, False])
def test_refresh_sees_only_new_control_settings_and_keeps_other_lines(installation, trailing_newline):
    root, _ = installation
    original = ORIGINAL if trailing_newline else ORIGINAL.rstrip(b"\n")
    # Stop deterministically after recording the successful refresh and Compose call.
    record_refresh_and_compose(root)
    result = run_toggle(installation, original=original)
    assert result.returncode == 72, result.stderr
    expected = (b"# Installed settings\nSPACEWORKS_RUN_FRONTEND=yes\n"
                b"SECRET_KEY='keep me'\nHTTP_PORT=8081\n# Last setting\n"
                b"CONTROL_PLANE_PROXY='true'\n"
                b"CONTROL_PLANE_ALLOW_CIDRS='10.0.0.0/8 192.0.2.1'\n")
    seen = root / "refresh-1.env"
    assert seen.read_bytes() == expected
    assert (root / ".env.before-control-plane").read_bytes() == original
    if os.name != "nt":
        assert seen.stat().st_mode & 0o777 == 0o600


@pytest.mark.parametrize("layer,extra,args,message", [
    ("tls", b"TLS_HTTPS_PORT=8443\n", ["--control-plane", "on", "--tunnel-port", "8443"],
     "already a published"),
    ("none", b"", ["--control-plane", "on"], "API-only"),
])
def test_post_rewrite_preflight_restores_environment_without_applying(installation, layer, extra, args, message):
    root, _ = installation
    original = ORIGINAL + extra
    if layer == "none":
        original = original.replace(b"SPACEWORKS_RUN_FRONTEND=yes", b"SPACEWORKS_RUN_FRONTEND=no")
    result = run_toggle(installation, original=original, layer=layer, args=args)
    assert result.returncode == 64, result.stderr
    assert message in result.stderr
    assert "previous .env was restored" in result.stderr
    assert "Applying failed" not in result.stderr
    assert (root / ".env").read_bytes() == original
    assert (root / ".env.before-control-plane").read_bytes() == original
    assert_no_refresh(root)


def test_compose_failure_refreshes_original_settings_and_restarts_on_rollback(installation):
    root, _ = installation
    record_refresh_and_compose(root)
    result = run_toggle(installation)
    assert result.returncode == 72, result.stderr
    assert (root / ".env").read_bytes() == ORIGINAL
    assert (root / "refresh-count").read_text().strip() == "2"
    assert (root / "refresh-1.env").read_bytes() != ORIGINAL
    assert (root / "refresh-2.env").read_bytes() == ORIGINAL
    commands = (root / "compose.log").read_text().splitlines()
    assert len(commands) == 2
    assert commands[0] == commands[1]
    assert "bundled up -d" in commands[0]
    assert "Rolled back to the previous control-plane settings." in result.stderr
    assert "Rollback incomplete" not in result.stderr


def test_rollback_refresh_failure_restores_env_and_prints_recovery_steps(installation):
    root, _ = installation
    record_refresh_and_compose(root)
    result = run_toggle(installation, TEST_ROLLBACK_REFRESH_FAIL="1")
    assert result.returncode == 72, result.stderr
    assert (root / ".env").read_bytes() == ORIGINAL
    assert (root / "refresh-count").read_text().strip() == "2"
    assert (root / "refresh-2.env").read_bytes() == ORIGINAL
    assert len((root / "compose.log").read_text().splitlines()) == 1
    assert "Rollback incomplete (refreshing topology records failed)" in result.stderr
    assert "cp -p .env.before-control-plane .env" in result.stderr
    assert "bash scripts/apply-settings.sh" in result.stderr
    assert "scripts/spaceworks-compose.sh bundled up -d --pull never" in result.stderr
    assert "Rolled back to the previous control-plane settings." not in result.stderr


def test_refresh_stops_at_first_failed_topology_record(tmp_path):
    result = subprocess.run([BASH, "-c", '''
source "$TEST_HELPER"
record_compose_config() {
  printf '%s\\n' "$1" >> records
  [[ "$1" != compose-topology-tls.json ]] || return 73
}
# Deliberately call in a conditional: errexit must not hide missing propagation.
if refresh_compose_config; then exit 0; else exit "$?"; fi
'''], cwd=tmp_path, env={**os.environ,
        "TEST_HELPER": (ROOT / "scripts/setup-host-orchestration.sh").as_posix()},
        capture_output=True, text=True, timeout=10)
    assert result.returncode == 73, result.stderr
    assert (tmp_path / "records").read_text().splitlines() == [
        "compose-topology.json", "compose-topology-build.json", "compose-topology-tls.json",
    ]


def test_live_lock_refuses_before_environment_backup_or_rewrite(installation):
    root, env = installation
    (root / ".env").write_bytes(ORIGINAL)
    # Bash's parent stays alive while apply runs; this also works for Git Bash PIDs.
    result = subprocess.run([BASH, "-c", '''
mkdir .spaceworks-update.lock
printf '%s %s\\n' "$$" "$(date +%s)" > .spaceworks-update.lock/owner
bash scripts/apply-settings.sh --control-plane on
status=$?
[[ -f .spaceworks-update.lock/owner ]] || exit 99
exit "$status"
'''], cwd=root, env=env, capture_output=True, text=True, timeout=15)
    assert result.returncode != 0, result.stderr
    assert "Another update owns" in result.stderr
    assert (root / ".env").read_bytes() == ORIGINAL
    assert not (root / ".env.before-control-plane").exists()
    assert not (root / "refreshed").exists()
    assert not (root / "compose-called").exists()
    assert not (root / "docker.log").exists()
    assert not (root / "backups").exists()


def test_rewrite_replaces_export_prefixed_and_indented_assignments(installation):
    root, _ = installation
    record_refresh_and_compose(root)
    original = (b"SPACEWORKS_RUN_FRONTEND=yes\nexport CONTROL_PLANE_PROXY=false\n"
                b"  CONTROL_PLANE_ALLOW_CIDRS='1.2.3.4'\n")
    result = run_toggle(installation, original=original)
    assert result.returncode == 72, result.stderr
    assert (root / "refresh-1.env").read_bytes() == (
        b"SPACEWORKS_RUN_FRONTEND=yes\nCONTROL_PLANE_PROXY='true'\n"
        b"CONTROL_PLANE_ALLOW_CIDRS='10.0.0.0/8 192.0.2.1'\n")


def test_record_refuses_when_deployment_layers_are_invalid(tmp_path):
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    (scripts / "compose-deployment.sh").write_text(
        "append_deployment_layers() { return 64; }\n", newline="\n")
    result = subprocess.run([BASH, "-c", '''
source "$TEST_HELPER"
docker() { echo docker >> docker-called; }
ROOT="$PWD"
if record_compose_config compose-topology.json; then exit 0; else exit "$?"; fi
'''], cwd=tmp_path, env={**os.environ,
        "TEST_HELPER": (ROOT / "scripts/setup-host-orchestration.sh").as_posix()},
        capture_output=True, text=True, timeout=10)
    assert result.returncode == 64, result.stderr
    assert not (tmp_path / "docker-called").exists()

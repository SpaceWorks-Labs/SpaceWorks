"""Settings preflights must finish before refreshing the installation's authority."""
import os
from pathlib import Path
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[2]
BASH = shutil.which("bash")
pytestmark = pytest.mark.skipif(not BASH, reason="requires bash")


def write_script(path, source):
    path.write_text("#!/bin/bash\n" + source, encoding="utf-8", newline="\n")
    path.chmod(0o755)


@pytest.fixture
def installation(tmp_path):
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    for name in ("apply-settings.sh", "install-owner.sh", "compose-deployment.sh",
                 "spaceworks-repository.sh", "update-lock.sh"):
        (scripts / name).write_text((ROOT / "scripts" / name).read_text(), newline="\n")
    lib = tmp_path / "frontend/docker/control-plane-allowlist.sh"
    lib.parent.mkdir(parents=True)
    lib.write_text((ROOT / "frontend/docker/control-plane-allowlist.sh").read_text(), newline="\n")
    # Mark the refresh seam: refusals must never source it or reach Compose.
    write_script(scripts / "setup-host-orchestration.sh", '''
refresh_compose_config() { echo refreshed > "$ROOT/refreshed"; exit 96; }
''')
    write_script(scripts / "spaceworks-compose.sh", 'echo compose > "$ROOT/compose-called"; exit 97\n')
    bins = tmp_path / "bin"
    bins.mkdir()
    write_script(bins / "flock", "exit 0\n")
    write_script(bins / "curl", "exit 98\n")
    write_script(bins / "docker", '''
printf '%s\\n' "$*" >> "$TEST_DOCKER_LOG"
case "$1" in
  ps)
    [[ "$*" == *"label=com.docker.compose.project.working_dir=$SPACEWORKS_UPDATE_INSTALL_DIR"* ]] || exit 91
    case "$*" in
      *label=com.docker.compose.service=backend*)
        [[ "${TEST_APP_MISSING:-0}" == 1 ]] || echo backend-cid ;;
      *label=com.docker.compose.service=frontend*) echo frontend-cid ;;
    esac ;;
  inspect)
    container="${@: -1}"
    if [[ "$3" == *com.docker.compose.project* ]]; then echo settings-test
    elif [[ "$container" == backend-cid ]]; then echo 'registry.example:5000/team/backend:v1 sha256:backend'
    elif [[ "$container" == frontend-cid ]]; then
      echo "registry.example:5000/team/frontend:${TEST_FRONTEND_TAG:-v1} sha256:frontend"
    else exit 92; fi ;;
  image)
    case "${@: -1}" in
      registry.example:5000/team/backend:v1) echo sha256:backend ;;
      registry.example:5000/team/frontend:v1)
        [[ "${TEST_REPOINTED:-0}" == 1 ]] && echo sha256:replacement || echo sha256:frontend ;;
      *) exit 93 ;;
    esac ;;
  *) exit 94 ;;
esac
''')
    ops = tmp_path / "ops"
    ops.mkdir()
    (ops / "compose-topology.json").write_text("original record\n", newline="\n")
    (ops / "database-pointer.env").write_text("original pointer\n", newline="\n")
    env = {key: value for key, value in os.environ.items()
           if not key.startswith(("SPACEWORKS_", "MAKERSPACE_", "CONTROL_PLANE_", "COMPOSE_"))}
    env.update({"PATH": os.pathsep.join((str(bins), str(Path(BASH).parent), os.environ["PATH"])),
                "SPACEWORKS_UPDATE_INSTALL_DIR": tmp_path.as_posix(),
                "SPACEWORKS_OPS_HOST_DIR": ops.as_posix(),
                "TEST_DOCKER_LOG": (tmp_path / "docker.log").as_posix()})
    return tmp_path, env


def apply(installation, layer="none", settings="", args=(), **changes):
    root, env = installation
    frontend = "" if "SPACEWORKS_RUN_FRONTEND=" in settings else "SPACEWORKS_RUN_FRONTEND=yes\n"
    (root / ".env").write_text(frontend + settings, newline="\n")
    (root / ".spaceworks-layer").write_text(layer + "\n", newline="\n")
    return subprocess.run([BASH, "scripts/apply-settings.sh", *args], cwd=root, env={**env, **changes},
                           capture_output=True, text=True, timeout=15)


def assert_no_refresh(root):
    assert not (root / "refreshed").exists()
    assert not (root / "compose-called").exists()
    assert not (root / "backups").exists()
    assert not (root / ".spaceworks-update.lock").exists()
    assert (root / "ops/compose-topology.json").read_text() == "original record\n"
    assert (root / "ops/database-pointer.env").read_text() == "original pointer\n"


@pytest.mark.parametrize("layer,env_settings,message", [
    ("build", "", "build layers"), ("build-tls", "", "build layers"), ("saas", "", "saas"),
    ("none", "SPACEWORKS_RUN_FRONTEND=no\nCONTROL_PLANE_PROXY=true\n", "API-only"),
    # The single-box layer was removed; it is refused like any other unsupported layer.
    ("single", "", "release layers none and tls"),
    ("none", "CONTROL_PLANE_PROXY=yes\n", "CONTROL_PLANE_PROXY"),
    ("none", "CONTROL_PLANE_ALLOW_CIDRS=01.2.3.4\n", "CONTROL_PLANE_ALLOW_CIDRS"),
    ("none", "CONTROL_PLANE_TUNNEL_PORT=08080\n", "CONTROL_PLANE_TUNNEL_PORT"),
    ("tls", "CONTROL_PLANE_PROXY=*\n", "CONTROL_PLANE_PROXY"),
    # Recreating Caddy on a colliding port would take the public HTTPS listener down.
    ("tls", "CONTROL_PLANE_TUNNEL_PORT=443\n", "already a published"),
    ("tls", "TLS_HTTPS_PORT=8443\nCONTROL_PLANE_TUNNEL_PORT=8443\n", "already a published"),
    # Every install refreshes the TLS records too, so a colliding port is refused up front.
    ("none", "CONTROL_PLANE_TUNNEL_PORT=9001\n", "already a published"),
])
def test_unsupported_or_invalid_settings_refuse_before_refresh(installation, layer, env_settings, message):
    result = apply(installation, layer, env_settings)
    assert result.returncode == 64, result.stderr
    assert message in result.stderr
    assert_no_refresh(installation[0])
    assert not (installation[0] / "docker.log").exists()


def test_missing_flock_refuses_with_linux_guidance(installation):
    root, _ = installation
    minimal = root / "minimal-bin"
    minimal.mkdir()
    # A private PATH models a missing command even on Linux hosts that have flock.
    for name in ("dirname", "uname", "stat", "id"):
        executable = shutil.which(name)
        assert executable, name
        write_script(minimal / name, f'exec "{Path(executable).as_posix()}" "$@"\n')
    result = apply(installation, PATH=str(minimal))
    assert result.returncode == 64, result.stderr
    assert "Linux or WSL2" in result.stderr
    assert_no_refresh(root)


@pytest.mark.parametrize("changes,message", [
    ({"TEST_FRONTEND_TAG": "v2"}, "frontend has a different release tag"),
    ({"TEST_REPOINTED": "1"}, "repointed for frontend"),
    ({"TEST_APP_MISSING": "1"}, "backend service must be running"),
])
def test_image_identity_refusals_preserve_record_and_pointer(installation, changes, message):
    result = apply(installation, **changes)
    assert result.returncode == 64, result.stderr
    assert message in result.stderr
    assert_no_refresh(installation[0])


def test_matching_image_identity_reaches_refresh_and_preserves_recovery_backup(installation):
    # Positive control for the shim: matching registry ports/tags pass every preflight.
    result = apply(installation)
    root, _ = installation
    assert result.returncode == 96, result.stderr  # Deliberate stop at the refresh boundary.
    assert (root / "refreshed").exists()
    backup, = (root / "backups").glob("env-applied-*")
    assert backup.read_bytes() == (root / ".env").read_bytes()
    if os.name != "nt":
        assert backup.stat().st_mode & 0o777 == 0o600
    assert "Applying failed. Restore the .env" in result.stderr
    assert "The database was not touched." in result.stderr
    commands = (root / "docker.log").read_text().splitlines()
    assert any("label=com.docker.compose.project=settings-test" in command for command in commands)


@pytest.mark.parametrize("layer,env_settings,expected", [
    ("tls", "PUBLIC_DOMAIN=tools.example.org\n", ["https://tools.example.org:443", "--resolve", "tools.example.org:443:127.0.0.1", "-k"]),
    ("tls", "PUBLIC_DOMAIN=tools.example.org\nTLS_HTTPS_PORT=8443\n", ["https://tools.example.org:8443", "--resolve", "tools.example.org:8443:127.0.0.1", "-k"]),
    ("none", "PUBLIC_DOMAIN=tools.example.org\nENABLE_HTTPS=true\nHTTP_PORT=8080\n", ["http://127.0.0.1:8080", "-H", "Host: tools.example.org", "-H", "X-Forwarded-Proto: https"]),
    ("none", "ENABLE_HTTPS=false\n", ["http://127.0.0.1:80", "-H", "Host: 127.0.0.1"]),
    ("single", "ENABLE_HTTPS=false\nHTTP_PORT=8081\n", ["http://127.0.0.1:8081", "-H", "Host: 127.0.0.1"]),
    ("none", "PUBLIC_DOMAIN=api.example.org\nSPACEWORKS_RUN_FRONTEND=no\nENABLE_HTTPS=true\nAPI_PORT=9080\nHTTP_PORT=8080\n", ["http://127.0.0.1:9080", "-H", "Host: api.example.org", "-H", "X-Forwarded-Proto: https"]),
])
def test_probe_target_urls_and_headers(installation, layer, env_settings, expected):
    root, env = installation
    (root / ".env").write_text(env_settings, newline="\n")
    result = subprocess.run(
        [BASH, "-c", 'ROOT="$PWD"; source scripts/compose-deployment.sh; '
         'source scripts/apply-settings.sh; control_plane_probe_target "$1"', "probe", layer],
        cwd=root, env=env, capture_output=True, text=True, timeout=10,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == expected
    assert not (root / "docker.log").exists()
    assert_no_refresh(root)


@pytest.mark.parametrize("args", [
    ["--unknown"],
    ["--allow-cidrs", "10.0.0.0/8"],
    ["--tunnel-port", "8443"],
    ["--control-plane", "maybe"],
    ["--landing", "maybe"],
    ["--landing"],
    ["--control-plane", "off", "--allow-cidrs", "10.0.0.0/8"],
    ["--control-plane", "on", "--allow-cidrs", "10.0.0.0/33"],
    ["--control-plane", "on", "--tunnel-port", "0"],
    ["--control-plane", "on", "--tunnel-port", "070000"],
    ["--control-plane", "on", "--tunnel-port", "08443"],
])
def test_invalid_toggle_arguments_leave_environment_and_records_untouched(installation, args):
    settings = "# keep this order\nSECRET_KEY='unchanged'\nCONTROL_PLANE_PROXY='false'\n"
    result = apply(installation, settings=settings, args=args)
    root, _ = installation
    assert result.returncode == 64, result.stderr
    assert (root / ".env").read_bytes() == ("SPACEWORKS_RUN_FRONTEND=yes\n" + settings).encode()
    assert not (root / ".env.before-control-plane").exists()
    assert not (root / "docker.log").exists()
    assert_no_refresh(root)

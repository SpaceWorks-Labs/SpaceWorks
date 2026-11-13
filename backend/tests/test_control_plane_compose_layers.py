"""Exercise overlay selection and engine preflight without a Docker daemon."""
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
def deployment(tmp_path):
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    for name in ("compose-deployment.sh", "spaceworks-compose.sh", "spaceworks-repository.sh"):
        (scripts / name).write_text((ROOT / "scripts" / name).read_text(), newline="\n")
    # The wrapper sources installer/host-paths.sh since 5f5b3a93 (2026-10-18).
    (scripts / "installer").mkdir()
    (scripts / "installer" / "host-paths.sh").write_text(
        (ROOT / "scripts/installer/host-paths.sh").read_text(), newline="\n")
    bins = tmp_path / "bin"
    bins.mkdir()
    # Force the real wrapper through container validation, itself replaced by the Docker seam.
    write_script(bins / "python3", "exit 1\n")
    write_script(bins / "docker", '''
printf '%s\\n' "$*" >> "$TEST_DOCKER_LOG"
case "$1" in
  version) printf '%s\\n' "$TEST_ENGINE" ;;
  run) exit 0 ;;
  compose) printf '%s\\n' "$@" > "$TEST_COMPOSE_ARGS"
    env | grep -E '^(CONTROL_PLANE_|TLS_HTTPS?_PORT|MINIO_(API|CONSOLE)_PORT)' > "$TEST_COMPOSE_ARGS.env" || true ;;
  *) exit 97 ;;
esac
''')
    env = {key: value for key, value in os.environ.items()
           if not key.startswith(("SPACEWORKS_", "MAKERSPACE_", "CONTROL_PLANE_", "COMPOSE_"))}
    env.update({"PATH": os.pathsep.join((str(bins), str(Path(BASH).parent), os.environ["PATH"])),
                "SPACEWORKS_UPDATE_INSTALL_DIR": tmp_path.as_posix(),
                "SPACEWORKS_OPS_HOST_DIR": (tmp_path / "ops").as_posix(),
                "TEST_DOCKER_LOG": (tmp_path / "docker.log").as_posix(),
                "TEST_COMPOSE_ARGS": (tmp_path / "compose.args").as_posix(), "TEST_ENGINE": "28.0.0"})
    return tmp_path, env


def select(deployment, layer, port, frontend="no", storage="external"):
    root, env = deployment
    (root / ".env").write_text(
        f"SPACEWORKS_RUN_FRONTEND='{frontend}'\nSPACEWORKS_STORAGE='{storage}'\nCONTROL_PLANE_TUNNEL_PORT='{port}'\n",
        newline="\n",
    )
    return subprocess.run(
        [BASH, "-c", '''set -euo pipefail
ROOT="$PWD"
source scripts/compose-deployment.sh
COMPOSE_FILES=(base.yml)
append_deployment_layers "$1" "$ROOT"
printf '%s\\n' "$DEPLOYMENT_SUFFIX" "${COMPOSE_FILES[@]}"
''', "select", layer], cwd=root, env=env, capture_output=True, text=True, timeout=10,
    )


@pytest.mark.parametrize("layer", ["none", "single", "saas", "build", "build-saas", "tls", "build-tls"])
@pytest.mark.parametrize("port", ["", "8443"])
def test_tunnel_is_selected_only_for_tls_and_is_last(deployment, layer, port):
    result = select(deployment, layer, port)
    assert result.returncode == 0, result.stderr
    suffix, *files = result.stdout.splitlines()
    tls = layer.endswith("tls")
    tunnel = tls and bool(port)
    expected = ["base.yml", "docker/compose.api-only.yml"]
    if tls or layer.endswith("saas"):
        expected.append("docker/compose.api-only-edge.yml")
    expected.append("docker/compose.external-storage.yml")
    if tunnel:
        expected.append("docker/compose.control-tunnel.yml")
    assert [path.removeprefix(deployment[0].as_posix() + "/") for path in files] == expected
    assert suffix == "-api-only-external-storage" + ("-control-tunnel" if tunnel else "")
    assert not (deployment[0] / "docker.log").exists()  # Selection must never invoke Docker.


@pytest.mark.parametrize("port", ["0", "08080", "65536", "123456", "-1", "8x", "8;exit 0"])
@pytest.mark.parametrize("layer", ["tls", "build-tls", "none", "single", "saas"])
def test_invalid_ports_refuse_tls_but_are_ignored_by_other_layers(deployment, layer, port):
    result = select(deployment, layer, port)
    assert result.returncode == (64 if layer.endswith("tls") else 0), result.stderr
    if layer.endswith("tls"):
        assert "CONTROL_PLANE_TUNNEL_PORT" in result.stderr
    assert not (deployment[0] / "docker.log").exists()


def append(root, env, layer):
    script = 'ROOT="$PWD"; source scripts/compose-deployment.sh; COMPOSE_FILES=(); append_deployment_layers "$1" "$ROOT"'
    return subprocess.run([BASH, "-c", script, "select", layer], cwd=root, env=env,
                          capture_output=True, text=True, timeout=10)


@pytest.mark.parametrize("value", ["*", "t*", "?rue", "[tf]*", "yes", "True", "on"])
@pytest.mark.parametrize("layer", ["tls", "none", "single"])
def test_proxy_selector_is_an_exact_enum_because_caddy_imports_glob(deployment, layer, value):
    root, env = deployment
    (root / ".env").write_text(f"CONTROL_PLANE_PROXY='{value}'\n", newline="\n")
    result = append(root, env, layer)
    assert result.returncode == 64
    assert "CONTROL_PLANE_PROXY must be true or false" in result.stderr


@pytest.mark.parametrize("extra,port", [
    ("", "80"), ("", "443"), ("", "9000"), ("", "9001"),
    ("TLS_HTTPS_PORT='8443'\n", "8443"), ("TLS_HTTP_PORT='8080'\n", "8080"),
    ("MINIO_API_PORT='9100'\n", "9100"),
])
def test_tunnel_port_may_not_shadow_a_published_port_on_tls(deployment, extra, port):
    root, env = deployment
    (root / ".env").write_text(f"{extra}CONTROL_PLANE_TUNNEL_PORT='{port}'\n", newline="\n")
    tls = append(root, env, "tls")
    assert tls.returncode == 64 and "already a published" in tls.stderr
    assert append(root, env, "none").returncode == 0


@pytest.mark.parametrize("port", ["1", "65535"])
def test_tunnel_port_boundaries_with_no_other_optional_layers(deployment, port):
    result = select(deployment, "tls", port, frontend="yes", storage="bundled")
    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == ["-control-tunnel", "base.yml",
                                          f"{deployment[0].as_posix()}/docker/compose.control-tunnel.yml"]


@pytest.mark.parametrize("layer,port,version,refused", [
    ("tls", "8443", "27.5.1", True), ("build-tls", "8443", "27.5.1", True),
    ("tls", "8443", "", True), ("tls", "8443", "unavailable", True),
    ("tls", "8443", "28.0.0", False), ("tls", "8443", "29.1.0", False),
    ("tls", "", "27.5.1", False), ("none", "8443", "27.5.1", False),
    ("saas", "8443", "27.5.1", False),
    # "single" is refused before Docker runs; see tests/test_single_box_removal.py.
])
def test_wrapper_checks_engine_only_when_tunnel_selected(deployment, layer, port, version, refused):
    root, env = deployment
    (root / ".env").write_text(f"CONTROL_PLANE_TUNNEL_PORT='{port}'\n", newline="\n")
    (root / ".spaceworks-layer").write_text(layer + "\n", newline="\n")
    result = subprocess.run([BASH, "scripts/spaceworks-compose.sh", "bundled", "up", "-d"],
                            cwd=root, env={**env, "TEST_ENGINE": version},
                            capture_output=True, text=True, timeout=20)
    assert result.returncode == (64 if refused else 0), result.stderr
    commands = (root / "docker.log").read_text().splitlines()
    needs_check = layer.endswith("tls") and bool(port)
    assert any(command.startswith("version ") for command in commands) == needs_check
    if refused:
        assert "Docker Engine 28 or newer" in result.stderr
        assert len(commands) == 1
        assert not (root / "compose.args").exists()
    else:
        assert commands[-1].startswith("compose ")
        args = (root / "compose.args").read_text().splitlines()
        assert any("compose.control-tunnel.yml" in arg for arg in args) == needs_check
        if needs_check:
            files = [args[index + 1] for index, value in enumerate(args) if value == "-f"]
            assert files[-1].endswith("/docker/compose.control-tunnel.yml")


def test_wrapper_never_hands_unvalidated_shell_overrides_to_compose(deployment):
    # Shell exports outrank --env-file during Compose interpolation; only the validated .env may count.
    root, env = deployment
    (root / ".env").write_text("CONTROL_PLANE_PROXY='false'\nCONTROL_PLANE_TUNNEL_PORT='8443'\n", newline="\n")
    (root / ".spaceworks-layer").write_text("tls\n", newline="\n")
    overrides = {"CONTROL_PLANE_PROXY": "*", "CONTROL_PLANE_ALLOW_CIDRS": "0.0.0.0/0",
                 "CONTROL_PLANE_TUNNEL_PORT": "443", "TLS_HTTP_PORT": "8443", "TLS_HTTPS_PORT": "8443",
                 "MINIO_API_PORT": "8443", "MINIO_CONSOLE_PORT": "8443"}
    result = subprocess.run([BASH, "scripts/spaceworks-compose.sh", "bundled", "up", "-d"],
                            cwd=root, env={**env, **overrides}, capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stderr
    assert (root / "compose.args.env").read_text() == ""

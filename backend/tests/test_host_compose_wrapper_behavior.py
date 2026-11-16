"""Run the trusted wrapper's no-host-Python path with Docker as a local seam."""

import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
BASH = shutil.which("bash")
pytestmark = pytest.mark.skipif(not BASH, reason="requires bash")
# host-paths.sh requires state directories owned by root or by `id -u`; the fake reports
# the runner's own uid so the fixture's directories qualify. A root runner models 1000.
OPERATOR_UID = os.getuid() or 1000


def write_script(path, source):
    path.write_text("#!/bin/bash\n" + source, encoding="utf-8", newline="\n")
    path.chmod(0o755)


@pytest.fixture
def wrapper(tmp_path):
    snapshot = tmp_path / "snapshot"
    (snapshot / "scripts").mkdir(parents=True)
    shutil.copytree(ROOT / "scripts/installer", snapshot / "scripts/installer", ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copy(ROOT / "scripts/compose-deployment.sh", snapshot / "scripts/compose-deployment.sh")
    target = tmp_path / "installed"
    target.mkdir()
    ops = tmp_path / "ops"
    ops.mkdir()
    bins = tmp_path / "bin"
    bins.mkdir()
    (target / ".env").write_text("POSTGRES_APP_PASSWORD=secret\n", encoding="utf-8", newline="\n")
    (target / "docker-compose.prod.yml").write_text("services: {}\n", encoding="utf-8", newline="\n")
    source = (ROOT / "scripts/spaceworks-compose.sh").read_text(encoding="utf-8")
    # Model an absent binary independently of Python installed on the test host.
    source = source.replace("command -v python3 >/dev/null 2>&1", '[[ "${TEST_PYTHON_AVAILABLE:-1}" == 1 ]]')
    write_script(snapshot / "scripts/spaceworks-compose.sh", source)
    for name in ("spaceworks-repository.sh", "compose-deployment.sh"):
        shutil.copy(ROOT / "scripts" / name, snapshot / "scripts" / name)
    write_script(bins / "python3", '''
printf 'host-python\\n' >> "$TEST_ORDER"
exit 1
''')
    write_script(bins / "id", f'''
case "$1" in
  -u|-g) echo {OPERATOR_UID} ;;
  -G) echo '{OPERATOR_UID} 998' ;;
esac
''')
    write_script(bins / "docker", '''
printf '%s\\n' "$1" >> "$TEST_ORDER"
case "$1" in
  run)
    printf '%s\\n' "$@" > "$TEST_RUN_ARGUMENTS"
    printf '%s\\n' "${MSYS_NO_PATHCONV:-}" > "$TEST_NO_PATHCONV"
    exit "${TEST_VALIDATION_FAILURE:-0}" ;;
  compose)
    printf '%s\\n' "$@" > "$TEST_COMPOSE_ARGUMENTS"
    printf '%s %s\\n' "${DATABASE_URL:-unset}" "${SPACEWORKS_DB_POINTER_GENERATION:-unset}" > "$TEST_POINTER_ENV" ;;
esac
''')
    environment = {
        **os.environ, "PATH": os.pathsep.join((str(bins), str(Path(BASH).parent), os.environ["PATH"])),
        "SPACEWORKS_UPDATE_INSTALL_DIR": target.as_posix(),
        "SPACEWORKS_OPS_HOST_DIR": ops.as_posix(),
        "SPACEWORKS_COMPOSE_LAYER": "none", "SPACEWORKS_COMPOSE_BUILD_LAYER": "0",
        "HOST_CONFIG_IMAGE": "ghcr.io/spaceworks-labs/spaceworks-backend:0.5.0-main.2.bbbbbbbbbbbb",
        "TEST_ORDER": (tmp_path / "order").as_posix(),
        "TEST_RUN_ARGUMENTS": (tmp_path / "run-args").as_posix(),
        "TEST_COMPOSE_ARGUMENTS": (tmp_path / "compose-args").as_posix(),
        "TEST_POINTER_ENV": (tmp_path / "pointer-env").as_posix(),
        "TEST_NO_PATHCONV": (tmp_path / "pathconv").as_posix(),
        "DATABASE_URL": "ambient-secret-database", "SPACEWORKS_DB_POINTER_GENERATION": "ambient-generation",
    }
    environment.pop("SPACEWORKS_STATIC_ENV_FILE", None)
    environment.pop("MAKERSPACE_IMAGE_TAG", None)
    return tmp_path, environment


def run_wrapper(wrapper, **changes):
    root, environment = wrapper
    return subprocess.run(
        [BASH, "snapshot/scripts/spaceworks-compose.sh", "bundled", "up", "-d"],
        cwd=root, env={**environment, **changes}, capture_output=True, text=True, timeout=30,
    )


@pytest.mark.parametrize("available", ["0", "1"])
def test_missing_or_old_host_python_uses_container_validation_before_compose(wrapper, available):
    result = run_wrapper(wrapper, TEST_PYTHON_AVAILABLE=available)
    root, environment = wrapper
    assert result.returncode == 0, result.stderr
    order = (root / "order").read_text().splitlines()
    assert order == (["host-python"] if available == "1" else []) + ["run", "compose"]
    arguments = (root / "run-args").read_text().splitlines()
    assert arguments[:6] == ["run", "--rm", "--network", "none", "--read-only", "--user"]
    assert f"{OPERATOR_UID}:{OPERATOR_UID}" in arguments
    assert arguments.count("--group-add") == 2 and "998" in arguments
    assert environment["HOST_CONFIG_IMAGE"] in arguments
    assert f"{environment['SPACEWORKS_UPDATE_INSTALL_DIR']}:/repo:ro" in arguments
    assert f"{environment['SPACEWORKS_UPDATE_INSTALL_DIR']}/.env:/static.env:ro" in arguments
    assert f"{environment['SPACEWORKS_OPS_HOST_DIR']}:/ops:ro" in arguments
    assert any(argument.endswith("/snapshot/scripts/..:/validation-code:ro") for argument in arguments)
    assert "SPACEWORKS_UPDATE_INSTALL_DIR=/repo" in arguments
    assert "/validation-code/scripts/validate-compose-wrapper.py" in arguments
    assert "/repo/docker-compose.prod.yml" in arguments
    assert (root / "pathconv").read_text().strip() == "1"
    compose = (root / "compose-args").read_text().splitlines()
    assert compose == [
        "compose", "--env-file", f"{environment['SPACEWORKS_UPDATE_INSTALL_DIR']}/.env",
        "--env-file", f"{environment['SPACEWORKS_OPS_HOST_DIR']}/database-pointer.env",
        "-f", f"{environment['SPACEWORKS_UPDATE_INSTALL_DIR']}/docker-compose.prod.yml", "up", "-d",
    ]
    assert (root / "pointer-env").read_text().strip() == "unset unset"


def test_failed_container_validation_never_runs_compose(wrapper):
    result = run_wrapper(wrapper, TEST_PYTHON_AVAILABLE="0", TEST_VALIDATION_FAILURE="73")
    root, _ = wrapper
    assert result.returncode == 73
    assert (root / "order").read_text().splitlines() == ["run"]
    assert not (root / "compose-args").exists()


def test_setup_initializes_database_pointer_using_pulled_image_without_host_python(tmp_path):
    (tmp_path / "scripts").mkdir()
    shutil.copy(ROOT / "scripts/compose-deployment.sh", tmp_path / "scripts/compose-deployment.sh")
    bins = tmp_path / "bin"
    bins.mkdir()
    write_script(bins / "python3", 'echo "host Python called" >&2; exit 98\n')
    write_script(bins / "docker", '''
printf '%s\\n' "$*" >> "$TEST_DOCKER_LOG"
case "$*" in
  *"-f /ops/database-pointer.env"*) exit 1 ;;
  *"/repo/scripts/bundled-database-url.py"*) printf 'postgresql://test-only/database\\n' ;;
  *"initialize-pointer"*)
    read -r database_url
    [[ "$database_url" == postgresql://test-only/database ]] || exit 99 ;;
esac
''')
    # The real root `docker run` creates the shared operation lock; the seam cannot.
    (tmp_path / "ops").mkdir()
    (tmp_path / "ops/operation.lock").touch()
    write_script(tmp_path / "setup-probe.sh", '''
set -euo pipefail
ROOT="$TEST_REPO_ROOT"
HOST_CONFIG_IMAGE="backend:main-test"
SPACEWORKS_HOST_CONFIG_BUILD=0
SPACEWORKS_OPS_HOST_DIR="$PWD/ops"
SPACEWORKS_HOST_STATE_DIR="$PWD/state"
source "$TEST_SETUP_HELPER"
prepare_compose_wrapper
''')
    result = subprocess.run(
        [BASH, "setup-probe.sh"], cwd=tmp_path,
        env={**os.environ, "PATH": os.pathsep.join((str(bins), str(Path(BASH).parent), os.environ["PATH"])),
             "TEST_DOCKER_LOG": (tmp_path / "docker.log").as_posix(),
             "TEST_REPO_ROOT": ROOT.as_posix(),
             "TEST_SETUP_HELPER": (ROOT / "scripts/setup-host-orchestration.sh").as_posix()},
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, result.stderr
    commands = (tmp_path / "docker.log").read_text().splitlines()
    assert commands[0] == "pull backend:main-test"
    helper = next(command for command in commands if "bundled-database-url.py" in command)
    assert "--entrypoint python" in helper and "backend:main-test" in helper
    assert any("initialize-pointer" in command for command in commands)
    assert "host Python called" not in result.stderr


@pytest.mark.parametrize("command", ["up", "pull"])
def test_wrapper_records_api_only_and_external_storage_in_every_invocation(wrapper, command):
    root, environment = wrapper
    target = root / "installed"
    (target / ".env").write_text("SPACEWORKS_RUN_FRONTEND='no'\nSPACEWORKS_STORAGE='external'\n")
    result = subprocess.run([BASH, "snapshot/scripts/spaceworks-compose.sh", "bundled", command],
        cwd=root, env={**environment, "TEST_PYTHON_AVAILABLE": "0"}, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    validation = (root / "run-args").read_text()
    args = (root / "compose-args").read_text()
    assert "compose-topology-api-only-external-storage.json" in validation
    assert "compose.api-only.yml" in args and "compose.external-storage.yml" in args


@pytest.mark.parametrize("saved,expected", [("tls", "build-tls"), ("saas", "build-saas")])
def test_build_adds_to_saved_https_layer_instead_of_hiding_it(wrapper, saved, expected):
    root, _ = wrapper
    (root / "installed/.spaceworks-layer").write_text(saved + "\n")
    result = run_wrapper(wrapper, SPACEWORKS_COMPOSE_LAYER="", SPACEWORKS_COMPOSE_BUILD_LAYER="1")
    assert result.returncode == 0, result.stderr
    args = (root / "compose-args").read_text()
    assert "compose.build.yml" in args and f"compose.{saved}.yml" in args
    validation = (root / "run-args").read_text()
    assert f"compose-topology-{expected}.json" in validation

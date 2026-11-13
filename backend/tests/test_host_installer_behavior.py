"""Real bootstrap against a loopback immutable release fixture; no Docker daemon.

The host commands are seams. This tests release trust, answers, privilege routing
and failure/resume; it cannot substitute for the Q lane's real Ubuntu/DinD/VM gate.
"""
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import threading

import pytest

ROOT = Path(__file__).resolve().parents[2]
BASH = shutil.which("bash")
# The modelled non-root operator is the runner itself, so the files the installer creates
# are owned by the uid its fake `id` reports. A root runner still models uid 1000.
OPERATOR_UID = os.getuid() or 1000
VERSION = (ROOT / "VERSION").read_text().strip() + "-main.2.bbbbbbbbbbbb"
COMMIT = "b" * 40
pytestmark = pytest.mark.skipif(not BASH or not shutil.which("curl"), reason="requires Bash and curl")


def write_script(path, source):
    path.write_text("#!/usr/bin/env bash\n" + source, newline="\n")
    path.chmod(0o755)


@pytest.fixture
def installer(tmp_path):
    bins, source = tmp_path / "bin", tmp_path / "release-source"
    bins.mkdir(); source.mkdir()
    manifest = subprocess.run([BASH, "-c", 'source "$HELPER"; host_bundle_files; printf "%s\\n" "${HOST_BUNDLE_FILES[@]}"'],
        env={**os.environ, "HELPER": (ROOT / "scripts/install-host-bundle.sh").as_posix()},
        capture_output=True, text=True, check=True).stdout.splitlines()
    for relative in manifest:
        target = source / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if relative == "deploy/contracts/programmes.json" and not (ROOT / relative).exists():
            # Opaque installer-copy fixture, not programme/runtime acceptance.
            target.write_text('{"schema_version":1,"installer_test_fixture":true}\n')
        else:
            shutil.copy(ROOT / relative, target)
        target.chmod(0o755 if target.suffix == ".sh" else 0o644)
    runtime = source / "scripts/installer/install-runtime.sh"
    runtime.write_text(runtime.read_text().replace("/etc/os-release", '"$TEST_OS_RELEASE"')
        .replace('! -w "$write_path"', '"${TEST_DIRECTORY_WRITABLE:-1}" == 0')
        .replace("/dev/tty", '"$TEST_TTY"')
        .replace('printf \'%s\' "$1" > "$TEST_TTY"', 'printf \'%s\' "$1" > "$TEST_PROMPT"')
        .replace('command -v docker >/dev/null 2>&1', '[[ "${TEST_DOCKER_INSTALLED:-1}" == 1 || -f "$TEST_DOCKER_SENTINEL" ]]'), newline="\n")
    # The re-entry menu answer feeds the selected action through install-finish.sh.
    finish = source / "scripts/installer/install-finish.sh"
    finish.write_text(finish.read_text().replace("/dev/tty", '"$TEST_TTY"'), newline="\n")
    preflight = source / "scripts/installer/host-preflight.sh"
    preflight.write_text(preflight.read_text().replace("/etc/os-release", '"$TEST_OS_RELEASE"')
        .replace('! -w "$write_path"', '"${TEST_DIRECTORY_WRITABLE:-1}" == 0')
        .replace('command -v docker >/dev/null 2>&1', '[[ "${TEST_DOCKER_INSTALLED:-1}" == 1 || -f "$TEST_DOCKER_SENTINEL" ]]'), newline="\n")
    questions = source / "scripts/setup-questions.sh"
    questions.write_text(questions.read_text().replace("[[ -d /run/systemd/system ]]", "true"), newline="\n")
    write_script(source / "setup.sh", '''
set -euo pipefail
if [[ "${SPACEWORKS_DEPLOYMENT_PROFILE:-full}" == free ]]; then
  printf 'setup free args=%s\\n' "$*" >> "$TEST_HOST_LOG"; exit 0
fi
source .spaceworks-answers
printf 'setup uid=%s group=%s repository=%s\\n' "${TEST_UID:-1000}" "${TEST_GROUP:-none}" "$SPACEWORKS_REPOSITORY" >> "$TEST_HOST_LOG"
cp .spaceworks-answers "$TEST_ANSWERS_COPY"
stat -c %a .spaceworks-answers > "$TEST_ANSWERS_MODE"
if [[ ! -f .env ]]; then (umask 077; printf 'SECRET_KEY=stable-fixture-key\\n' > .env); fi
python3 scripts/installer/state.py phase --root "$PWD" --repository "$SPACEWORKS_REPOSITORY" --release "$MAKERSPACE_IMAGE_TAG" --phase environment
[[ "${TEST_SETUP_FAIL:-0}" != 1 ]] || exit 23
[[ ! "$INSTALL_RUNNER" =~ ^[Yy] ]] || bash scripts/install-runner.sh
rm -f .spaceworks-answers
python3 scripts/installer/state.py phase --root "$PWD" --repository "$SPACEWORKS_REPOSITORY" --release "$MAKERSPACE_IMAGE_TAG" --phase complete
''')
    write_script(source / "scripts/update.sh", 'printf "update uid=%s group=%s root=%s %s\\n" "${TEST_UID:-1000}" "${TEST_GROUP:-none}" "$SPACEWORKS_UPDATE_INSTALL_DIR" "$*" >> "$TEST_HOST_LOG"\n')
    write_script(source / "scripts/install-runner.sh", 'printf "runner uid=%s group=%s\\n" "${TEST_UID:-1000}" "${TEST_GROUP:-none}" >> "$TEST_HOST_LOG"\n')
    write_script(source / "scripts/spaceworks-compose.sh", "echo '{\"name\":\"installer-fixture\"}'\n")
    blobs, archive_buffer = [], io.BytesIO()
    with tarfile.open(fileobj=archive_buffer, mode="w:gz") as bundle:
        for file in sorted(source.rglob("*")):
            if not file.is_file():
                continue
            relative, raw = file.relative_to(source).as_posix(), file.read_bytes()
            blobs.append({"path": relative, "type": "blob", "size": len(raw),
                          "mode": "100755" if file.stat().st_mode & 0o111 else "100644",
                          "sha": hashlib.sha1(f"blob {len(raw)}\0".encode() + raw).hexdigest()})
            bundle.add(file, arcname="release/" + relative, recursive=False)
    requests = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            requests.append(self.path)
            parts = self.path.split("/")
            if self.path.startswith("/api/repos/"):
                repo = "/".join(parts[3:5])
                release = {"tag_name": "v" + VERSION, "draft": False, "prerelease": False,
                    "published_at": "2026-10-18T00:00:00Z", "html_url": f"https://github.com/{repo}/releases/tag/v{VERSION}"}
                if "/git/trees/" in self.path:
                    value = {"truncated": False, "tree": blobs}
                elif "/commits/" in self.path:
                    value = {"sha": COMMIT}
                else:
                    value = release if "/releases/tags/" in self.path else [release]
                raw = json.dumps(value).encode()
            elif self.path.startswith("/raw/"):
                raw = (source / "/".join(parts[5:])).read_bytes()
            elif self.path.startswith("/github/"):
                raw = archive_buffer.getvalue()
            else:
                self.send_error(404); return
            self.send_response(200); self.send_header("Content-Length", str(len(raw))); self.end_headers()
            self.wfile.write(raw)

        def log_message(self, *_):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    write_script(bins / "python3", 'exec "$TEST_PYTHON" "$@"\n')
    write_script(bins / "uname", '[[ "$1" == -m ]] && echo x86_64 || echo Linux\n')
    write_script(bins / "id", 'case "$1" in -u|-g) echo "${TEST_UID:-1000}" ;; -un) echo operator ;; esac\n')
    write_script(bins / "sudo", 'printf "sudo %s\\n" "$*" >> "$TEST_HOST_LOG"\nexport TEST_UID=0\nexec "$@"\n')
    write_script(bins / "sg", 'printf "sg %s\\n" "$*" >> "$TEST_HOST_LOG"\nexport TEST_GROUP=docker\nexec sh -c "$3"\n')
    for name in ("chown", "usermod", "systemctl"):
        write_script(bins / name, f'printf "{name} %s\\n" "$*" >> "$TEST_HOST_LOG"\n')
    write_script(bins / "apt-get", 'printf "apt-get uid=%s %s\\n" "${TEST_UID:-1000}" "$*" >> "$TEST_HOST_LOG"\n[[ "$*" != *docker.io* ]] || touch "$TEST_DOCKER_SENTINEL"\n')
    write_script(bins / "docker", '''
printf 'docker uid=%s group=%s %s\\n' "${TEST_UID:-1000}" "${TEST_GROUP:-none}" "$*" >> "$TEST_HOST_LOG"
if [[ "$1" == info ]]; then
  [[ "${TEST_UID:-1000}" == 0 || "${TEST_GROUP:-}" == docker || "${TEST_DOCKER_ACCESS:-0}" == 1 ]] || exit 1
  [[ "$*" != *DockerRootDir* ]] || printf '%s\\n' "$TEST_DOCKER_ROOT"
  exit 0
fi
if [[ "$*" == *'config --format json'* ]]; then
  [[ "${TEST_BAD_COMPOSE:-0}" != 1 ]] || exit 1
  echo '{"services":{"probe":{"ports":[],"environment":{"ONLY":"replacement"}}}}'
elif [[ "$*" == *'up --help'* ]]; then echo '--wait --no-deps --force-recreate --remove-orphans'; fi
''')
    write_script(bins / "df", 'printf "Filesystem 1024-blocks Used Available Capacity Mounted on\\nmock 999999999 1 999999998 1%% /\\n"\n')
    write_script(bins / "awk", '[[ "$*" != *wanted=* ]] || exit 0\nexec "$TEST_REAL_AWK" "$@"\n')
    answers = tmp_path / "answers.json"
    answers.write_text(json.dumps({"schema_version": 1, "confirmed": True, "answers": {
        "ORG_NAME": "Installer Test", "ADMINEMAIL": "owner@example.org", "ADMINPASS": "private-test-password"}}))
    answers.chmod(0o600)
    (tmp_path / "os-release").write_text("ID=ubuntu\n")
    (tmp_path / "tty").write_text("1\n")
    env = {**os.environ, "PATH": str(bins) + os.pathsep + os.environ["PATH"],
        "SPACEWORKS_DIR": (tmp_path / "installed").as_posix(), "TMPDIR": tmp_path.as_posix(),
        "SPACEWORKS_INSTALL_TEST_MODE": "1", "SPACEWORKS_INSTALL_TEST_API": f"http://127.0.0.1:{server.server_port}",
        "TEST_HOST_LOG": (tmp_path / "host.log").as_posix(), "TEST_OS_RELEASE": (tmp_path / "os-release").as_posix(),
        "TEST_UID": str(OPERATOR_UID), "TEST_PYTHON": sys.executable, "TEST_REAL_AWK": shutil.which("awk"), "TEST_TTY": (tmp_path / "tty").as_posix(),
        "TEST_DOCKER_ROOT": tmp_path.as_posix(), "TEST_DOCKER_SENTINEL": (tmp_path / "docker-installed").as_posix(), "TEST_PROMPT": (tmp_path / "prompt").as_posix(),
        "SPACEWORKS_INSTALL_TEST_TTY": (tmp_path / "tty").as_posix(),
        "TEST_ANSWERS_COPY": (tmp_path / "answers-copy").as_posix(), "TEST_ANSWERS_MODE": (tmp_path / "answers-mode").as_posix()}
    env.pop("SPACEWORKS_REPOSITORY", None)
    env.pop("SPACEWORKS_DEPLOYMENT_PROFILE", None)
    env.pop("MAKERSPACE_IMAGE_TAG", None)
    try:
        yield tmp_path, env, requests
    finally:
        server.shutdown(); server.server_close(); thread.join(timeout=5)


def run(installer, *args, **changes):
    """Run stage 2 (install-entry.sh) from a copy of the fixture bundle, as install.sh leaves it.

    install.sh itself (download, SHA256SUMS, cosign) is covered by test_release_asset_installer.py.
    """
    root, env, _ = installer
    stage = root / f"stage-{len(list(root.glob('stage-*')))}"
    shutil.copytree(root / "release-source", stage / "runtime")
    staged = {"SPACEWORKS_STAGED_DIR": stage.as_posix(), "SPACEWORKS_STAGED_VERSION": VERSION,
              "SPACEWORKS_STAGED_COMMIT": COMMIT, "SPACEWORKS_STAGED_SHA256": "c" * 64}
    result = subprocess.run([BASH, str(stage / "runtime/scripts/installer/install-entry.sh"), *args], cwd=root,
                             env={**env, **staged, **changes}, capture_output=True, text=True, timeout=45)
    return result, (root / "host.log").read_text() if (root / "host.log").exists() else ""


def fresh(installer, **changes):
    return run(installer, "--non-interactive", "--answers-file", str(installer[0] / "answers.json"), **changes)


def test_user_writable_install_still_uses_sudo_for_docker_access(installer):
    result, log = fresh(installer)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "sudo docker info" in log and "sudo usermod -aG docker operator" in log
    assert f"setup uid={OPERATOR_UID} group=docker" in log
    assert (installer[0] / "installed/.spaceworks-version").read_text().strip() == VERSION


def test_root_with_sudo_user_keeps_setup_root_owned_and_runner_opt_in(installer):
    result, log = fresh(installer, TEST_UID="0", SUDO_USER="operator")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "sudo " not in log and "setup uid=0 group=none" in log and "runner uid=" not in log


def test_existing_docker_group_access_needs_no_host_escalation(installer):
    result, log = fresh(installer, TEST_GROUP="docker")
    assert result.returncode == 0, result.stderr
    assert "sudo " not in log and "usermod " not in log


def test_directory_escalation_returns_fresh_install_to_the_operator(installer):
    result, log = fresh(installer, TEST_DIRECTORY_WRITABLE="0")
    assert result.returncode == 0, result.stderr
    assert "sudo cp -a" in log and f"sudo chown {OPERATOR_UID}:{OPERATOR_UID}" in log and f"setup uid={OPERATOR_UID} group=docker" in log


@pytest.mark.parametrize("args", [("--repo", "Example-Owner/MyFork"), ("--repo=Example-Owner/MyFork",)])
def test_repo_flag_selects_the_fork_without_the_environment_variable(installer, args):
    result, log = run(installer, *args, "--non-interactive", "--answers-file", str(installer[0] / "answers.json"))
    assert result.returncode == 0, result.stderr
    assert "repository=Example-Owner/MyFork" in log


def test_fork_repository_is_used_for_download_and_setup(installer):
    result, log = fresh(installer, SPACEWORKS_REPOSITORY="Example-Owner/MyFork")
    assert result.returncode == 0, result.stderr
    assert "repository=Example-Owner/MyFork" in log


def test_distribution_metadata_never_replaces_the_pinned_release(installer):
    # Real /etc/os-release also defines VERSION and NAME; reading the distribution
    # family must not overwrite the release the installer verified.
    (installer[0] / "os-release").write_text(
        'NAME="Ubuntu"\nVERSION="24.04.5 LTS (Noble Numbat)"\nID=ubuntu\nID_LIKE=debian\n')
    result, log = fresh(installer)
    assert result.returncode == 0, result.stderr
    assert "setup uid=" in log


def test_missing_required_answer_fails_before_packages_or_target_creation(installer):
    (installer[0] / "answers.json").write_text('{"schema_version":1,"confirmed":true,"answers":{}}')
    result, log = fresh(installer)
    assert result.returncode != 0 and not (installer[0] / "installed").exists()
    assert "usermod " not in log and "setup uid=" not in log


def test_confirmed_answers_are_private_deleted_and_not_on_command_line(installer):
    result, log = fresh(installer)
    assert result.returncode == 0, result.stderr
    assert (installer[0] / "answers-mode").read_text().strip() == "600"
    assert "private-test-password" not in log + result.stdout + result.stderr
    assert not (installer[0] / "installed/.spaceworks-answers").exists()


def test_failed_setup_resumes_same_release_without_rotating_environment(installer):
    result, _ = fresh(installer, TEST_SETUP_FAIL="1")
    assert result.returncode == 23, result.stderr
    root = installer[0] / "installed"
    assert not (root / ".spaceworks-version").exists()
    original = (root / ".env").read_bytes()
    result, _ = run(installer, "--resume", "--non-interactive")
    assert result.returncode == 0, result.stderr
    assert (root / ".env").read_bytes() == original
    assert (root / ".spaceworks-version").read_text().strip() == VERSION


def test_compose_feature_failure_refuses_before_target_writes(installer):
    result, _ = fresh(installer, TEST_BAD_COMPOSE="1")
    assert result.returncode != 0 and not (installer[0] / "installed").exists()


@pytest.mark.parametrize("args", [("--repo",), ("--unknown",), ("--non-interactive",)])
def test_invalid_cli_has_no_provider_or_host_effects(installer, args):
    result, log = run(installer, *args)
    assert result.returncode == 64 and not log and not installer[2]


def test_arbitrary_nonempty_target_is_never_overwritten(installer):
    target = installer[0] / "installed"
    target.mkdir(); (target / "operator.txt").write_text("keep")
    result, _ = fresh(installer)
    assert result.returncode != 0 and (target / "operator.txt").read_text() == "keep"


def test_fresh_server_installs_docker_with_sudo_before_group_setup(installer):
    result, log = fresh(installer, TEST_DOCKER_INSTALLED="0")
    assert result.returncode == 0, result.stderr
    assert log.index("apt-get uid=0 install -y docker.io") < log.index("sudo usermod -aG docker operator")
    assert f"setup uid={OPERATOR_UID} group=docker" in log


@pytest.mark.parametrize("choice,expected", [("1", "--force --no-module-changes"), ("2", "--modules-only"), ("3", "--force --modules")])
def test_existing_module_and_update_menu_keeps_installed_state(installer, choice, expected):
    target = installer[0] / "installed"
    (target / "scripts").mkdir(parents=True)
    shutil.copy(installer[0] / "release-source/scripts/update.sh", target / "scripts/update.sh")
    (target / ".spaceworks-version").write_text(VERSION)
    (installer[0] / "tty").write_text(choice + "\n")
    result, log = run(installer)
    assert result.returncode == 0, result.stderr
    assert expected in log and "setup uid=" not in log
    assert (target / ".spaceworks-version").read_text() == VERSION


def test_existing_cancel_is_distinct_from_success(installer):
    target = installer[0] / "installed"
    target.mkdir(); (target / ".spaceworks-version").write_text(VERSION)
    (installer[0] / "tty").write_text("4\n")
    result, log = run(installer)
    assert result.returncode == 130 and "Cancelled" in result.stdout
    assert "setup uid=" not in log and "update uid=" not in log


def test_fresh_runner_opt_in_uses_install_owner_and_docker_group(installer):
    path = installer[0] / "answers.json"
    value = json.loads(path.read_text())
    value["answers"]["INSTALL_RUNNER"] = "Y"
    path.write_text(json.dumps(value))
    result, log = fresh(installer)
    assert result.returncode == 0, result.stderr
    assert f"runner uid={OPERATOR_UID} group=docker" in log


def test_full_profile_ignores_free_tick_secret_and_keeps_full_install_flow(installer):
    result, log = fresh(installer, SPACEWORKS_DEPLOYMENT_PROFILE="full", FREE_TICK_SECRET="unused-fixture-secret")
    assert result.returncode == 0, result.stderr
    assert "setup uid=" in log and "unused-fixture-secret" not in result.stdout + result.stderr + log
    assert (installer[0] / "installed/.spaceworks-version").read_text().strip() == VERSION


def test_free_profile_is_an_explicit_opt_in_that_starts_no_full_stack(installer):
    # Owner decision: the VPS installer OFFERS the free profile; full stays the default.
    result, log = fresh(installer, SPACEWORKS_DEPLOYMENT_PROFILE="free")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "setup free args=--non-interactive" in log
    assert "Prepared the free profile" in result.stdout
    assert not (installer[0] / "installed/.spaceworks-version").exists()


def test_unknown_profile_refuses_before_any_effect(installer):
    result, log = fresh(installer, SPACEWORKS_DEPLOYMENT_PROFILE="paid")
    assert result.returncode == 64 and not log and not installer[2]
    assert not (installer[0] / "installed").exists()

"""Runner installation with stubbed host/network boundaries and no Docker daemon."""
import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
BASH = shutil.which("bash")
pytestmark = pytest.mark.skipif(not BASH, reason="requires bash")
TOKEN = "short_lived_registration_secret"


def write_script(path, source):
    path.write_text("#!/usr/bin/env bash\n" + source, encoding="utf-8", newline="\n")
    path.chmod(0o755)


@pytest.fixture
def runner_host(tmp_path):
    scripts, bins = tmp_path / "scripts", tmp_path / "bin"
    scripts.mkdir()
    bins.mkdir()
    for name in ("install-owner.sh", "spaceworks-repository.sh", "runner-release.py"):
        shutil.copy(ROOT / "scripts" / name, scripts / name)
    source = (ROOT / "scripts/install-runner.sh").read_text()
    source = source.replace('[[ ! -d /run/systemd/system ]]', 'false')
    source = source.replace('</dev/tty', '<"$TEST_INPUT"')
    (scripts / "install-runner.sh").write_text(source, newline="\n")
    config = '''
printf 'config %s\\n' "$*" >> "$TEST_LOG"
[[ "$ACTIONS_RUNNER_INPUT_TOKEN" == "$TEST_TOKEN" ]] || exit 88
[[ "$*" != *"$TEST_TOKEN"* ]] || exit 89
if [[ "${TEST_UID:-1000}" == 0 ]]; then [[ "$RUNNER_ALLOW_RUNASROOT" == 1 ]] || exit 90; fi
if [[ "${1:-}" == remove ]]; then rm -f .runner; else
  [[ ! -f .runner ]] || exit 92
  cp service-template.sh svc.sh
  echo '{}' > .runner
  echo 'LANG=en_US.UTF-8' > .env
fi
'''
    service = '''
printf 'service %s\\n' "$*" >> "$TEST_LOG"
[[ "$1" != install ]] || echo 'actions.runner.test.service' > .service
[[ "$1" != uninstall ]] || rm -f .service
'''
    archive = tmp_path / "release.tar.gz"
    with tarfile.open(archive, "w:gz") as output:
        for name, content in (("config.sh", config), ("service-template.sh", service)):
            payload = ("#!/usr/bin/env bash\nset -eu\n" + content).encode()
            info = tarfile.TarInfo(name)
            info.size, info.mode = len(payload), 0o755
            output.addfile(info, io.BytesIO(payload))
    checksum = hashlib.sha256(archive.read_bytes()).hexdigest()
    name = "actions-runner-linux-x64-2.999.0.tar.gz"
    metadata = {"tag_name": "v2.999.0", "draft": False, "prerelease": False,
                "published_at": "2026-10-14T00:00:00Z", "body": f"| {name} | {checksum} |",
                "assets": [{"name": name, "browser_download_url":
                    f"https://github.com/actions/runner/releases/download/v2.999.0/{name}"}]}
    (tmp_path / "release.json").write_text(json.dumps(metadata))
    (tmp_path / "input").write_text(TOKEN + "\n")
    write_script(bins / "uname", '[[ "$1" == -m ]] && echo "${TEST_ARCH:-x86_64}" || echo "${TEST_OS:-Linux}"\n')
    write_script(bins / "id", 'case "$1" in -u) echo "${TEST_UID:-1000}";; -un) echo operator;; esac\n')
    write_script(bins / "stat", '[[ "$2" != %u ]] || { echo "${TEST_UID:-1000}"; exit; }; echo operator\n')
    write_script(bins / "hostname", 'echo maker-server\n')
    write_script(bins / "sudo", 'printf "sudo %s\\n" "$*" >> "$TEST_LOG"; exec "$@"\n')
    write_script(bins / "install", 'cd "$(dirname "${@: -1}")"; mkdir "$(basename "${@: -1}")"\n')
    write_script(bins / "docker", '[[ "${TEST_DOCKER:-yes}" == yes ]]\n')
    write_script(bins / "systemctl", 'exit 0\n')
    write_script(bins / "python3", 'set -o pipefail; "$TEST_PYTHON" "$@" | tr -d \'\\r\'\n')
    write_script(bins / "curl", '''
printf 'curl %s\\n' "$*" >> "$TEST_LOG"
[[ "$*" == *releases/latest* ]] && source_file="$TEST_METADATA" || source_file="$TEST_ARCHIVE"
while (($#)); do
  if [[ "$1" == -o ]]; then cp "$source_file" "$2"; exit; fi
  shift
done
exit 91
''')
    env = {**os.environ, "PATH": os.pathsep.join((str(bins), str(Path(BASH).parent), os.environ["PATH"])),
           "SPACEWORKS_REPOSITORY": "Example-Owner/MyFork",
           "SPACEWORKS_RUNNER_DIR": (tmp_path / "runner").as_posix(),
           "TEST_LOG": (tmp_path / "host.log").as_posix(), "TEST_TOKEN": TOKEN,
           "TEST_INPUT": (tmp_path / "input").as_posix(), "TEST_PYTHON": sys.executable,
           "TEST_METADATA": (tmp_path / "release.json").as_posix(),
           "TEST_ARCHIVE": archive.as_posix()}
    if os.name == "nt":
        env["SPACEWORKS_RUNNER_DIR"] = "/" + tmp_path.drive[0].lower() + tmp_path.as_posix()[2:] + "/runner"
    return tmp_path, env


def invoke(host, *arguments, **overrides):
    root, env = host
    return subprocess.run([BASH, str(root / "scripts/install-runner.sh"), *arguments],
                          cwd=root, env={**env, **overrides}, input="", text=True,
                          capture_output=True, timeout=30)


def test_registration_uses_private_environment_and_installs_owner_service(runner_host):
    root, _ = runner_host
    result = invoke(runner_host)
    assert result.returncode == 0, result.stdout + result.stderr
    log = (root / "host.log").read_text()
    assert "--url https://github.com/Example-Owner/MyFork" in log
    assert "--name maker-server-spaceworks --labels spaceworks-prod --unattended --replace" in log
    assert "service install operator" in log and "service start" in log
    assert "sudo bash ./svc.sh install operator" in log
    assert TOKEN not in log + result.stdout + result.stderr
    for path in (root / "runner").rglob("*"):
        if path.is_file():
            assert TOKEN.encode() not in path.read_bytes()
    assert "LANG=en_US.UTF-8\nSPACEWORKS_DIR=" in (root / "runner/.env").read_text()
    assert "SPACEWORKS_DEPLOY = true" in result.stdout
    assert "Require approval for all external contributors" in result.stdout


def test_checksum_mismatch_refuses_before_unpacking_or_prompting(runner_host):
    root, _ = runner_host
    metadata = json.loads((root / "release.json").read_text())
    metadata["body"] = metadata["body"].replace(hashlib.sha256((root / "release.tar.gz").read_bytes()).hexdigest(), "0" * 64)
    (root / "release.json").write_text(json.dumps(metadata))
    result = invoke(runner_host)
    assert result.returncode != 0 and "SHA-256 mismatch" in result.stderr
    assert "token (hidden)" not in result.stdout
    assert not (root / "runner").exists()


def test_missing_checksum_is_refused(runner_host):
    root, _ = runner_host
    metadata = json.loads((root / "release.json").read_text())
    metadata["body"] = "No checksums"
    (root / "release.json").write_text(json.dumps(metadata))
    result = invoke(runner_host)
    assert result.returncode != 0 and "SHA-256" in result.stderr
    assert not (root / "runner").exists()


def test_remove_uses_removal_token_and_uninstalls_service(runner_host):
    root, _ = runner_host
    result = invoke(runner_host)
    assert result.returncode == 0, result.stderr
    (root / "host.log").write_text("")
    result = invoke(runner_host, "--remove")
    assert result.returncode == 0, result.stderr
    log = (root / "host.log").read_text()
    assert log.index("service stop") < log.index("service uninstall") < log.index("config remove")
    assert TOKEN not in log + result.stdout + result.stderr
    assert not (root / "runner/.runner").exists()
    assert "curl " not in log


def test_root_owned_install_can_configure_and_remove(runner_host):
    result = invoke(runner_host, TEST_UID="0")
    assert result.returncode == 0, result.stderr
    assert invoke(runner_host, "--remove", TEST_UID="0").returncode == 0


def test_non_linux_skips_without_registering(runner_host):
    root, _ = runner_host
    result = invoke(runner_host, TEST_OS="Darwin")
    assert result.returncode == 0 and "only Linux" in result.stdout
    assert not (root / "runner").exists()


def test_owner_without_docker_access_is_refused(runner_host):
    result = invoke(runner_host, TEST_DOCKER="no")
    assert result.returncode != 0 and "Docker access" in result.stderr


def test_explicit_reinstall_removes_existing_registration_first(runner_host):
    root, _ = runner_host
    first = invoke(runner_host)
    assert first.returncode == 0, first.stderr
    (root / "host.log").write_text("")
    result = invoke(runner_host)
    assert result.returncode == 0, result.stderr
    log = (root / "host.log").read_text()
    assert log.index("service uninstall") < log.index("config remove") < log.index("config --url")
    assert TOKEN not in log + result.stdout + result.stderr


def test_arm64_download_and_registration(runner_host):
    root, _ = runner_host
    source = (root / "release.json").read_text().replace("linux-x64", "linux-arm64")
    (root / "release.json").write_text(source)
    result = invoke(runner_host, TEST_ARCH="aarch64")
    assert result.returncode == 0, result.stderr
    assert "actions-runner-linux-arm64" in (root / "host.log").read_text()


def test_draft_runner_release_is_refused(runner_host):
    root, _ = runner_host
    data = json.loads((root / "release.json").read_text())
    data["draft"] = True
    (root / "release.json").write_text(json.dumps(data))
    result = invoke(runner_host)
    assert result.returncode != 0 and "published stable" in result.stderr
    assert not (root / "runner").exists()


@pytest.mark.parametrize("document", [None, [], {"tag_name": []},
    {"tag_name": "v2.338.0", "draft": False, "prerelease": False,
     "published_at": "2026-10-06T13:55:00Z", "assets": [None]}])
def test_malformed_runner_metadata_fails_cleanly(document):
    result = subprocess.run([sys.executable, str(ROOT / "scripts/runner-release.py"), "x64"],
                            input=json.dumps(document), text=True, capture_output=True)
    assert result.returncode != 0
    assert result.stderr.startswith("ERROR:") and "Traceback" not in result.stderr

"""Run the actual host updater with local command seams and no Docker/network access."""

import json
import re
import tarfile
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
BASH = shutil.which("bash")
pytestmark = pytest.mark.skipif(not BASH or not (ROOT / "scripts/update.sh").exists(), reason="requires bash and repository scripts")
OLD = "0.5.0-main.1.aaaaaaaaaaaa"
NEW = "0.5.0-main.2.bbbbbbbbbbbb"


def write_script(path, source):
    path.write_text("#!/usr/bin/env bash\n" + source, encoding="utf-8", newline="\n")
    path.chmod(0o755)


@pytest.fixture
def host(tmp_path):
    scripts, bins = tmp_path / "scripts", tmp_path / "bin"
    scripts.mkdir()
    bins.mkdir()
    (tmp_path / "ops").mkdir()
    (tmp_path / "ops/database-pointer.env").write_text("fixture pointer\n")
    manifest = (ROOT / "scripts/install-host-bundle.sh").read_text(encoding="utf-8")
    files = re.search(r"HOST_BUNDLE_FILES=\((.*?)\n  \)", manifest, re.S)[1].split()
    for name in files:
        destination = tmp_path / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        if name == "deploy/contracts/programmes.json" and not (ROOT / name).exists():
            destination.write_text('{"schema_version":1,"installer_test_fixture":true}\n')
        else:
            shutil.copy(ROOT / name, destination)
    (tmp_path / ".spaceworks-version").write_text(OLD)
    (tmp_path / ".env").write_text("BACKUP_ARCHIVE_VERIFY_PUBLIC_KEY=fixture-key\n")
    write_script(bins / "df", 'printf "Filesystem 1024-blocks Used Available Capacity Mounted on\\nmock 999999999 1 999999998 1%% /\\n"\n')
    # Peak-capacity admission inspects the running backend image and measures the
    # Docker data filesystem from inside it before any backup or copy.
    write_script(bins / "docker", '\n[[ "$1" != info ]] || { printf "%s\\n" "$TEST_DOCKER_ROOT"; exit 0; }\n[[ "$*" != *record-config* || "${TEST_FAILURE:-}" != config ]] || exit 1\nif [[ "$1" == inspect && "$*" == *"{{.Image}}"* ]]; then printf "sha256:%064d\\n" 0; exit 0; fi\nif [[ "$1" == inspect && "$*" == *Health* ]]; then echo "running|healthy"; exit 0; fi\n[[ "$1" != inspect ]] || echo "${TEST_JOB_STATE:-exited 0}"\nif [[ "$1" == run && "$*" == *statvfs* ]]; then echo 1099511627776; fi\nexit 0\n')
    write_script(bins / "sleep", "exit 0\n")
    # Polling retirement must never read or rewrite the test operator's real jobs.
    write_script(bins / "crontab", '[[ "$1" == -l ]] && exit 1\nexit 99\n')
    write_script(bins / "curl", '''
printf '%s\\n' "$*" >> "$TEST_CURL_LOG"
for ((arg=1; arg<=$#; arg++)); do
  if [[ "${!arg}" == -o ]]; then next=$((arg + 1)); exec > "${!next}"; break; fi
done
[[ "${TEST_FAILURE:-}" != github ]] || exit 22
if [[ "$*" == *"/commits/v"* ]]; then
  printf '{"sha":"%s0000000000000000000000000000"}\\n' "${TEST_RELEASE##*.}"
  exit 0
fi
if [[ "$*" == *"/archive/"* ]]; then
  [[ "${TEST_FAILURE:-}" != archive ]] || exit 22
  while [[ "$1" != -o ]]; do shift; done
  cp "$TEST_BUNDLE" "$2"
  exit 0
fi
if [[ "$*" == *"/git/trees/"* ]]; then
  while [[ "$1" != -o ]]; do shift; done
  cp "$TEST_TREE" "$2"; exit 0
fi
if [[ -n "${TEST_RELEASE_JSON:-}" && "$TEST_RELEASE_JSON" == "["* && "$*" == *"/releases/tags/"* ]]; then
  # The verified bundle fetch asks for the selected tag alone, as GitHub serves it.
  "$TEST_PYTHON" -c 'import json, sys; print(json.dumps(next(r for r in json.loads(sys.argv[1]) if r["tag_name"] == sys.argv[2])))' "$TEST_RELEASE_JSON" "$(url="${!#}"; printf "%s" "${url##*/releases/tags/}")"
  exit $?
fi
if [[ -n "${TEST_RELEASE_JSON:-}" ]]; then printf '%s\\n' "$TEST_RELEASE_JSON"; exit 0; fi
if [[ "$*" == *"/releases/tags/"* ]]; then
  printf '{"tag_name":"v%s","draft":false,"prerelease":false,"published_at":"2026-10-10T10:00:00Z","html_url":"https://github.com/%s/releases/tag/v%s"}\\n' "$TEST_RELEASE" "${SPACEWORKS_REPOSITORY:-SpaceWorks-Labs/SpaceWorks}" "$TEST_RELEASE"
  exit 0
fi
printf '[{"tag_name":"v%s","draft":false,"prerelease":false,"published_at":"2026-10-10T10:00:00Z","html_url":"https://github.com/%s/releases/tag/v%s"}]\\n' "$TEST_RELEASE" "${SPACEWORKS_REPOSITORY:-SpaceWorks-Labs/SpaceWorks}" "$TEST_RELEASE"
''')
    write_script(scripts / "spaceworks-compose.sh", '''
printf '%s\\n' "$*" >> "$TEST_COMPOSE_LOG"
printf '%s: %s\\n' "${MAKERSPACE_IMAGE_TAG:-current}" "$*" >> "$TEST_IMAGE_LOG"
case "$*" in
  *"config --format json"*) echo '{"name":"fixture"}' ;;
  *"Validate a release commit"*)
    while [[ "$1" != -c ]]; do shift; done
    shift; "$TEST_PYTHON" -c "$@"; exit $? ;;
  *"Choose the newest published immutable main release"*)
    while [[ "$1" != -c ]]; do shift; done
    shift; "$TEST_PYTHON" -c "$@"; exit $? ;;
  *" --active-proof") echo "${TEST_DATABASE_NAME:-spaceworks_after_restore}|16384|1b4e28ba-2fa1-4d2e-8f1c-3d7a1e0f9b21" ;;
  *"urlsplit"*) echo "${TEST_DATABASE_NAME:-spaceworks_after_restore}" ;;
  *"Read-only proof that missing legacy key material"*) echo '1|1' ;;
  *"Read-only deployment size measurement"*) echo '{"database_bytes": 1024, "object_bytes": 0}' ;;
  *"pg_database_size"*) echo 1024 ;;
  *"pg_dump"*) [[ "${TEST_FAILURE:-}" != backup ]] || exit 1 ;;
  *"ps -a -q"*) echo job-container ;;
  *"ps -q "*) echo service-container ;;
  *"exec -T"*"python -c"*)
    if [[ "${TEST_FAILURE:-}" == readiness && "${MAKERSPACE_IMAGE_TAG:-}" == "$TEST_RELEASE" ]]; then exit 1; fi ;;
  *"pull "*)
    if [[ "${TEST_FAILURE:-}" == pull ]]; then exit 1; fi ;;
esac
exit 0
''')
    # Package the full selected host runtime, preserving the fake Compose seam.
    # Its updater marker proves execution and installation came from the download.
    (scripts / "update.sh").write_text((scripts / "update.sh").read_text(encoding="utf-8") + "# selected host bundle\n", encoding="utf-8", newline="\n")
    bundle = tmp_path / "selected.tar.gz"
    with tarfile.open(bundle, "w:gz") as archive:
        for name in files:
            if name == "VERSION":
                continue
            archive.add(tmp_path / name, arcname=f"release/{name}")
        import io
        content = b"0.5.0\n"
        entry = tarfile.TarInfo("release/VERSION")
        entry.size = len(content)
        archive.addfile(entry, io.BytesIO(content))
    tree = []
    with tarfile.open(bundle) as archive:
        for member in archive.getmembers():
            if member.isfile():
                import hashlib
                content = archive.extractfile(member).read()
                tree.append({"path": member.name.partition("/")[2], "type": "blob", "size": len(content),
                             "mode": "100755" if member.mode & 0o111 else "100644",
                             "sha": hashlib.sha1(f"blob {len(content)}\0".encode() + content).hexdigest()})
    (tmp_path / "tree.json").write_text(json.dumps({"truncated": False, "tree": tree}))
    # The installed launcher is deliberately older than the selected bundle.
    (scripts / "update.sh").write_text((ROOT / "scripts/update.sh").read_text(encoding="utf-8"), encoding="utf-8", newline="\n")
    environment = {
        **os.environ, "PATH": str(bins) + os.pathsep + os.environ["PATH"],
        "SPACEWORKS_OPS_HOST_DIR": (tmp_path / "ops").as_posix(),
        "TEST_COMPOSE_LOG": (tmp_path / "compose.log").as_posix(),
        "TEST_CURL_LOG": (tmp_path / "curl.log").as_posix(), "TEST_RELEASE": NEW,
        "TEST_PYTHON": Path(sys.executable).as_posix(),
        "TEST_TREE": (tmp_path / "tree.json").as_posix(), "TEST_DOCKER_ROOT": tmp_path.as_posix(),
        "TEST_BUNDLE": bundle.as_posix(), "TMPDIR": tmp_path.as_posix(),
        "TEST_IMAGE_LOG": (tmp_path / "images.log").as_posix(),
        "SPACEWORKS_COMPOSE_LAYER": "none", "SPACEWORKS_COMPOSE_BUILD_LAYER": "0",
    }
    environment.pop("MAKERSPACE_IMAGE_TAG", None)
    return tmp_path, environment


def run(host, *options, **overrides):
    root, environment = host
    result = subprocess.run(
        [BASH, str(root / "scripts/update.sh"), "--no-module-changes", *options],
        cwd=root, env={**environment, **overrides}, capture_output=True, text=True, timeout=30,
    )
    log = root / "compose.log"
    return result, log.read_text(encoding="utf-8") if log.exists() else ""


def test_success_finishes_and_releases_both_locks(host):
    result, log = run(host)
    root, _ = host
    assert result.returncode == 0, result.stderr
    assert (root / ".spaceworks-version").read_text(encoding="utf-8").strip() == NEW
    assert log.index("pg_dump") < log.index("pull ") < log.index("up -d --remove-orphans\n")
    assert "SPACEWORKS_BACKUP_DATABASE=spaceworks_after_restore" in log
    assert 'pg_dump -U "$POSTGRES_USER" "$SPACEWORKS_BACKUP_DATABASE" > "$raw"' in log
    assert "rm -f -s orchestration-init migrate orchestration-ready createbuckets" in log
    assert "update_control" not in log
    assert not (root / ".spaceworks-update.lock").exists()
    curl = (root / "curl.log").read_text(encoding="utf-8")
    assert "--max-time 30" in curl and "--retry 2" in curl


@pytest.mark.parametrize("failure", ["readiness"])
def test_failed_deployment_rolls_back_and_resets_the_version_marker(host, failure):
    result, log = run(host, TEST_FAILURE=failure)
    root, _ = host
    assert result.returncode != 0
    assert "Rollback complete" in result.stdout
    assert "up -d --no-deps backend live worker beat frontend" in log
    assert log.count("bundled up -d --remove-orphans\n") == 1
    assert (root / ".spaceworks-version").read_text(encoding="utf-8").strip() == OLD
    assert "rm -f -s" in log
    assert not (root / ".spaceworks-update.lock").exists()


@pytest.mark.parametrize("failure", ["github", "backup", "pull"])
def test_failed_provider_check_or_pull_keeps_the_previous_release(host, failure):
    result, log = run(host, TEST_FAILURE=failure)
    root, _ = host
    assert result.returncode != 0
    assert (root / ".spaceworks-version").read_text(encoding="utf-8").strip() == OLD
    assert "rm -f -s" not in log
    if failure == "backup":
        assert "pull " not in log
    assert not (root / ".spaceworks-update.lock").exists()


def test_noop_never_takes_a_backup_or_replaces_containers(host):
    result, log = run(host, TEST_RELEASE=OLD)
    assert result.returncode == 0
    assert "pg_dump" not in log and "pull " not in log
    assert (host[0] / ".spaceworks-version").read_text(encoding="utf-8") == OLD


@pytest.mark.parametrize("persisted", [False, True])
def test_removed_single_box_refuses_before_network_or_backup(host, persisted):
    if persisted:
        (host[0] / ".spaceworks-layer").write_text("single\n")
    result, log = run(host, SPACEWORKS_COMPOSE_LAYER="" if persisted else "single")
    assert result.returncode == 64
    assert "single-box install shape" in result.stderr
    assert not log and not (host[0] / "curl.log").exists()


def test_a_live_update_owner_is_refused_before_any_provider_call(host):
    root, _ = host
    lock = root / ".spaceworks-update.lock"
    lock.mkdir()
    (lock / "owner").write_text(f"{os.getpid()} 1\n")
    result, log = run(host)
    assert result.returncode != 0
    assert "Another update owns" in result.stderr
    assert log == "" and lock.exists()


def test_a_dead_update_owner_is_recovered(host):
    root, _ = host
    lock = root / ".spaceworks-update.lock"
    lock.mkdir()
    (lock / "owner").write_text("2147483647 1\n")
    result, _ = run(host)
    assert result.returncode == 0, result.stderr
    assert "Recovering the stale update lock" in result.stdout
    assert not lock.exists()


@pytest.mark.parametrize("version", [
    "0.5.0-beta.2.bbbbbbbbbbbb", "0.5.0-main.2.bbbbbbbb", "main", "latest",
])
def test_only_immutable_main_releases_can_change_images(host, version):
    result, log = run(host, TEST_RELEASE=version)
    assert result.returncode != 0
    assert "eligible published main release" in result.stderr
    assert "pull " not in log
    assert (host[0] / ".spaceworks-version").read_text().strip() == OLD
    assert not (host[0] / ".spaceworks-update.lock").exists()


def test_old_installed_backend_only_receives_published_main_candidates(host):
    releases = [
        {"tag_name": f"v{NEW}", "draft": False, "prerelease": False, "published_at": "2026-10-10T10:00:00Z", "html_url": f"https://github.com/SpaceWorks-Labs/SpaceWorks/releases/tag/v{NEW}"},
        {"tag_name": "v0.5.0-beta.999.cccccccccccc", "draft": False, "prerelease": False},
        {"tag_name": "v0.5.0-main.999.cccccccccccc", "draft": False, "prerelease": True},
        {"tag_name": "v0.5.0-main.999.dddddddddddd", "draft": True, "prerelease": False},
    ]
    result, log = run(host, TEST_RELEASE_JSON=json.dumps(releases))
    assert result.returncode == 0, result.stderr
    assert (host[0] / ".spaceworks-version").read_text().strip() == NEW
    assert "update_control" not in log


def test_no_main_release_refuses_before_claiming_or_taking_a_snapshot(host):
    result, log = run(host, TEST_RELEASE="0.5.0-beta.999.cccccccccccc")
    assert result.returncode != 0
    assert "eligible published main release" in result.stderr
    assert "pg_dump" not in log and "pull " not in log
    assert (host[0] / ".spaceworks-version").read_text().strip() == OLD
    assert not (host[0] / ".spaceworks-update.lock").exists()


def test_pinned_snapshot_updater_uses_its_wrapper_and_actual_install_marker(host):
    root, environment = host
    snapshot = root / "release-snapshot"
    shutil.copytree(root / "scripts", snapshot / "scripts")
    # Before backup the installed wrapper is intentionally used; after bundle setup the staged wrapper is used.
    result = subprocess.run(
        [BASH, str(snapshot / "scripts/update.sh"), "--no-module-changes"],
        cwd=root, env={**environment, "SPACEWORKS_UPDATE_INSTALL_DIR": root.as_posix()},
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, result.stderr
    assert (root / ".spaceworks-version").read_text().strip() == NEW
    assert not (snapshot / ".spaceworks-version").exists()
    assert "rm -f -s" in (root / "compose.log").read_text()
    assert not (root / ".spaceworks-update.lock").exists()


def test_root_owned_updater_reentry_keeps_absolute_script_path_after_cd(host):
    root, environment = host
    write_script(root / "bin/uname", "echo Linux\n")
    write_script(root / "bin/id", 'echo "${TEST_UID:-1000}"\n')
    write_script(root / "bin/stat", "echo 0\n")
    # Model sudo's own option parsing: install-owner.sh forwards --preserve-env=...
    # (installer environment continuity, 411b4aea) before the command.
    write_script(root / "bin/sudo", 'export TEST_UID=0; while [[ "${1:-}" == -* ]]; do shift; done; exec "$@"\n')
    result = subprocess.run(
        [BASH, f"{root.name}/scripts/update.sh", "--help"], cwd=root.parent,
        env={**environment, "TEST_UID": "1000"},
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, result.stderr
    assert "Root-owned install: continuing as root using sudo." in result.stdout
    assert "Usage: scripts/update.sh" in result.stdout
    assert not (root / ".spaceworks-update.lock").exists()


def test_fork_repository_changes_release_url_and_image_namespace(host):
    result, _ = run(host, SPACEWORKS_REPOSITORY="Example-Owner/MyFork")
    assert result.returncode == 0, result.stderr
    assert "repos/Example-Owner/MyFork/releases" in (host[0] / "curl.log").read_text()
    # The helpers receive the derived backend namespace for marker refresh.
    helper = (ROOT / "scripts/spaceworks-repository.sh").as_posix()
    result = subprocess.run([BASH, "-c", f'source "{helper}"; configure_release_repository; printf "%s %s" "$MAKERSPACE_BACKEND_IMAGE" "$MAKERSPACE_FRONTEND_IMAGE"'],
                            env={**host[1], "ROOT": host[0].as_posix(), "SPACEWORKS_REPOSITORY": "Example-Owner/MyFork"},
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert result.stdout == "ghcr.io/example-owner/spaceworks-backend ghcr.io/example-owner/spaceworks-frontend"


@pytest.mark.parametrize("state", ["exited 1", "running 0"])
def test_failed_or_running_one_shots_are_kept_for_inspection(host, state):
    result, log = run(host, TEST_JOB_STATE=state)
    assert result.returncode == 0, result.stderr
    assert "rm -f -s" not in log
    assert "Keeping orchestration-init" in result.stderr


def test_explicit_image_names_override_repository_defaults(host):
    helper = (ROOT / "scripts/spaceworks-repository.sh").as_posix()
    result = subprocess.run(
        [BASH, "-c", f'source "{helper}"; configure_release_repository; printf "%s %s" "$MAKERSPACE_BACKEND_IMAGE" "$MAKERSPACE_FRONTEND_IMAGE"'],
        env={**host[1], "ROOT": host[0].as_posix(), "SPACEWORKS_REPOSITORY": "Fork-Owner/Fork",
             "MAKERSPACE_BACKEND_IMAGE": "registry.example/api", "MAKERSPACE_FRONTEND_IMAGE": "registry.example/web"},
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout == "registry.example/api registry.example/web"


@pytest.mark.parametrize("repository", ["owner/repo/extra", "../repo", "owner/repo;touch", "owner/", "-owner/repo"])
def test_invalid_repository_refuses_before_network(host, repository):
    result, log = run(host, SPACEWORKS_REPOSITORY=repository)
    assert result.returncode != 0 and "GitHub owner/repo" in result.stderr
    assert not log and not (host[0] / "curl.log").exists()


def test_database_pointer_name_is_validated_before_backup(host):
    result, log = run(host, TEST_DATABASE_NAME="bad/name")
    assert result.returncode != 0
    assert "pg_dump" not in log and "pull " not in log


def test_configuration_refresh_failure_has_host_recovery_instructions(host):
    result, log = run(host, TEST_FAILURE="config")
    assert result.returncode != 0
    assert "Host configuration upgrade stopped before deployment" in result.stderr
    # The staged bundle always records its exact backup directory before the refresh.
    assert "Restored the exact previous host files" in result.stdout
    assert "database was not replaced" in result.stderr
    assert "bundled up -d --remove-orphans\n" not in log and "rm -f -s" not in log


@pytest.mark.parametrize("failure", ["", "readiness"])
def test_api_only_external_storage_updates_and_rolls_back_without_disabled_services(host, failure):
    root, _ = host
    with (root / ".env").open("a") as env:
        env.write("SPACEWORKS_RUN_FRONTEND='no'\nSPACEWORKS_STORAGE='external'\n")
    result, log = run(host, TEST_FAILURE=failure)
    assert result.returncode == (1 if failure else 0), result.stderr
    assert "frontend" not in log and "minio" not in log and "createbuckets" not in log
    assert "pull orchestration-init migrate orchestration-ready backend live worker beat api-edge" in log
    assert "rm -f -s orchestration-init migrate orchestration-ready" in log
    assert "update_control" not in log
    if failure:
        assert "up -d --no-deps backend live worker beat api-edge" in log
        assert (root / ".spaceworks-version").read_text().strip() == OLD
        assert "Rollback complete" in result.stdout
    assert not (root / ".spaceworks-update.lock").exists()


def test_single_box_external_storage_refuses_before_deployment(host):
    with (host[0] / ".env").open("a") as env:
        env.write("SPACEWORKS_STORAGE='external'\n")
    result, log = run(host, SPACEWORKS_COMPOSE_LAYER="single", TEST_FAILURE="readiness")
    assert result.returncode == 64 and "single-box install shape" in result.stderr
    assert not log


@pytest.mark.parametrize("failure", ["", "readiness"])
def test_api_only_update_and_failed_update_rollback_never_pull_website(host, failure):
    root, _ = host
    with (root / ".env").open("a", encoding="utf-8") as env:
        env.write("SPACEWORKS_RUN_FRONTEND='no'\nSPACEWORKS_STORAGE='external'\n")
    result, log = run(host, TEST_FAILURE=failure)
    assert result.returncode == (0 if not failure else 1), result.stderr
    pulls = [line for line in log.splitlines() if "pull " in line]
    assert pulls and all("frontend" not in line and "minio" not in line and "createbuckets" not in line for line in pulls)
    assert all("live" in line for line in pulls)


def test_selected_bundle_is_downloaded_validated_executed_and_installed(host):
    result, log = run(host, "--version", NEW, SPACEWORKS_REPOSITORY="Example-Owner/MyFork")
    assert result.returncode == 0, result.stderr
    root, _ = host
    assert "Continuing with host tooling from Example-Owner/MyFork" in result.stdout
    assert "# selected host bundle" in (root / "scripts/update.sh").read_text()
    assert "SPACEWORKS_REPOSITORY=Example-Owner/MyFork" in (root / ".env").read_text()
    urls = (root / "curl.log").read_text()
    assert f"repos/Example-Owner/MyFork/commits/v{NEW}" in urls
    assert f"Example-Owner/MyFork/archive/{NEW.split('.')[-1]}" in urls
    assert log.index("stop backend worker beat live") < log.index("up -d --remove-orphans")
    assert "up -d --no-deps --force-recreate frontend" in log
    assert not list(root.glob(".spaceworks-update.*"))


@pytest.mark.parametrize("version", ["0.5.0-main.0.bbbbbbbbbbbb", "0.5.0-main.1.bbbbbbbbbbbb", "0.4.9-main.3.bbbbbbbbbbbb"])
def test_force_and_explicit_version_cannot_downgrade_or_replace_same_run(host, version):
    result, log = run(host, "--force", "--version", version, TEST_RELEASE=version)
    assert result.returncode != 0 and "Refusing release downgrade" in result.stderr
    # Decision 219g: forward-only; the refusal names the restore-from-backup path.
    assert "forward-only" in result.stderr and "restore the pre-upgrade backup" in result.stderr
    assert "docs/install-and-update.md#rolling-back" in result.stderr
    assert "pg_dump" not in log and "stop backend" not in log
    assert "archive/" not in (host[0] / "curl.log").read_text()


def test_bad_archive_refuses_before_backup_or_configuration_replacement(host):
    (host[0] / "selected.tar.gz").write_bytes(b"invalid archive")
    result, log = run(host)
    # The selected bundle is now verified member by member against its Git tree.
    assert result.returncode != 0 and "Could not verify the complete selected release bundle" in result.stderr
    assert "pg_dump" not in log and "stop backend" not in log
    assert (host[0] / ".spaceworks-version").read_text() == OLD


def test_tls_edges_are_recreated_after_update_and_rollback(host):
    result, log = run(host, SPACEWORKS_COMPOSE_LAYER="tls", TEST_FAILURE="readiness")
    assert result.returncode != 0
    assert log.count("up -d --no-deps --force-recreate caddy") == 2
    assert log.count("up -d --no-deps --force-recreate frontend") == 2

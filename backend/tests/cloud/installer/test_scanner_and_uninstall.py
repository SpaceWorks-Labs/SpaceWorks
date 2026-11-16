"""Selected scanner topology and conservative retained-data file removal."""
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[4]
BASH = shutil.which("bash")
VERSION = "0.9.2-main.2.bbbbbbbbbbbb"


@pytest.mark.skipif(not BASH, reason="requires Bash")
@pytest.mark.parametrize("mode,expected", [("bundled", "UPLOAD_SCAN_POLICY=clamav"),
                                           ("external", "CLAMD_HOST=scanner.internal"),
                                           ("none", "UPLOAD_SCAN_POLICY=none")])
def test_scanner_selection_has_one_shared_policy_and_no_public_port(mode, expected):
    result = subprocess.run([BASH, "-c", '''set -euo pipefail
env_setting() { printf '%s=%s\n' "$1" "$2"; }
source "$HELPER"
write_setup_scanner_environment
'''], env={**os.environ, "HELPER": (ROOT / "scripts/installer/setup-scan.sh").as_posix(),
            "SETUP_SCAN_MODE": mode, "SETUP_CLAMD_HOST": "scanner.internal", "SETUP_CLAMD_PORT": "3310"},
        capture_output=True, text=True, timeout=10)
    assert result.returncode == 0 and expected in result.stdout
    assert ("COMPOSE_PROFILES=clamav" in result.stdout) is (mode == "bundled")
    assert "0.0.0.0" not in result.stdout


def install_record(root):
    files = {"setup.sh": b"original setup\n", "scripts/uninstall.sh": b"owned remover\n"}
    for relative, raw in files.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
    (root / ".spaceworks-version").write_text(VERSION)
    marker = root / ".spaceworks-managed-files.json"
    marker.write_text(json.dumps({"schema_version": 1, "root": str(root), "phase": "complete", "release": VERSION,
                                 "owner": root.stat().st_uid, "files": {name: hashlib.sha256(raw).hexdigest()
                                                                       for name, raw in files.items()}}))
    marker.chmod(0o600)
    return files


def remove_files(root, names, validate=False):
    command = [sys.executable, str(ROOT / "scripts/installer/uninstall-files.py"), str(root)]
    if validate:
        command.append("--validate")
    return subprocess.run(command, input="\n".join(names) + "\n", capture_output=True, text=True, timeout=10)


@pytest.mark.skipif(os.name == "nt", reason="POSIX ownership test; Windows ACL transport is tested separately")
def test_retained_data_uninstall_removes_only_unchanged_recorded_runtime(tmp_path):
    files = install_record(tmp_path)
    (tmp_path / ".env").write_text("SECRET_KEY=retained\n")
    (tmp_path / "setup.sh").write_text("operator modified\n")
    result = remove_files(tmp_path, files)
    assert result.returncode == 0, result.stderr
    assert (tmp_path / "setup.sh").read_text() == "operator modified\n"
    assert (tmp_path / ".env").read_text() == "SECRET_KEY=retained\n"
    assert not (tmp_path / "scripts/uninstall.sh").exists()


@pytest.mark.skipif(os.name == "nt", reason="requires POSIX symlink and owner semantics")
def test_uninstall_validates_all_paths_before_deleting_any_file(tmp_path):
    root, outside = tmp_path / "install", tmp_path / "outside"
    root.mkdir(); outside.mkdir()
    files = install_record(root)
    (outside / "keep.txt").write_text("outside data")
    (root / "redirect").symlink_to(outside, target_is_directory=True)
    result = remove_files(root, [*files, "redirect/keep.txt"])
    assert result.returncode == 1
    assert (root / "setup.sh").exists() and (root / "scripts/uninstall.sh").exists()
    assert (outside / "keep.txt").read_text() == "outside data"


@pytest.mark.skipif(os.name == "nt", reason="requires POSIX permissions")
def test_validate_only_has_no_effect_and_stale_release_refuses(tmp_path):
    files = install_record(tmp_path)
    result = remove_files(tmp_path, files, validate=True)
    assert result.returncode == 0 and all((tmp_path / name).exists() for name in files)
    (tmp_path / ".spaceworks-version").write_text("different-release")
    result = remove_files(tmp_path, files)
    assert result.returncode == 1 and all((tmp_path / name).exists() for name in files)


@pytest.mark.skipif(os.name == "nt", reason="requires POSIX permissions")
@pytest.mark.parametrize("case", ["project", "driver", "labels", "options", "valid"])
def test_purge_requires_recorded_project_and_independently_local_volumes(tmp_path, monkeypatch, case):
    install_record(tmp_path)
    marker = tmp_path / ".spaceworks-managed-files.json"
    record = json.loads(marker.read_text())
    record["project"] = "fixture"
    marker.write_text(json.dumps(record))
    monkeypatch.syspath_prepend(str(ROOT / "scripts/installer"))
    spec = importlib.util.spec_from_file_location("uninstall_admission", ROOT / "scripts/installer/uninstall-admission.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    config = {"name": "foreign" if case == "project" else "fixture", "services": {},
              "volumes": {"database": {"name": "fixture_database"}}}
    facts = {"Name": "fixture_database", "Driver": "nfs" if case == "driver" else "local",
             "Options": {"type": "nfs"} if case == "options" else {},
             "Labels": {"com.docker.compose.project": "foreign" if case == "labels" else "fixture",
                        "com.docker.compose.volume": "database"}}
    calls = []

    def docker(*args):
        calls.append(args)
        return "fixture_database\n" if args[1] == "ls" else json.dumps([facts])

    monkeypatch.setattr(module, "docker", docker)
    monkeypatch.setattr(sys, "argv", [str(module.__file__), str(tmp_path), "1"])
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(config)))
    if case == "valid":
        module.main()
    else:
        with pytest.raises(ValueError):
            module.main()
    if case == "project":
        assert not calls
    assert (tmp_path / "setup.sh").exists()

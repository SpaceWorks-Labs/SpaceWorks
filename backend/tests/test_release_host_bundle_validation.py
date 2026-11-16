"""Validate downloaded archive bytes before extraction or host execution."""
import io
import json
from pathlib import Path
import subprocess
import sys
import tarfile

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts/release-host-bundle.py"
REQUIRED = ("VERSION", "scripts/update.sh", "scripts/install-host-bundle.sh",
            "scripts/update-release-bundle.sh", "scripts/release-host-bundle.py",
            "docker-compose.prod.yml")


def validate(data, mode="archive", expected="0.5.0"):
    return subprocess.run([sys.executable, str(SCRIPT), mode, expected], input=data,
                          capture_output=True, timeout=10)


def bundle(extra=None, version=b"0.5.0\n"):
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode="w:gz") as archive:
        for name in REQUIRED:
            entry = tarfile.TarInfo(f"release/{name}")
            content = version if name == "VERSION" else b"fixture\n"
            entry.size = len(content)
            archive.addfile(entry, io.BytesIO(content))
        if extra is not None:
            archive.addfile(extra)
    return output.getvalue()


def test_complete_bundle_and_matching_commit_are_admitted():
    assert validate(bundle()).returncode == 0
    commit = "a" * 40
    assert validate(json.dumps({"sha": commit}).encode(), "commit", commit[:12]).returncode == 0


@pytest.mark.parametrize("name", ["release/../outside", "/absolute", "other-root/file"])
def test_unsafe_archive_paths_are_refused(name):
    assert validate(bundle(tarfile.TarInfo(name))).returncode != 0


def test_symlink_version_mismatch_and_incomplete_bundle_are_refused():
    link = tarfile.TarInfo("release/link")
    link.type = tarfile.SYMTYPE
    link.linkname = "scripts/update.sh"
    assert validate(bundle(link)).returncode != 0
    assert validate(bundle(version=b"0.4.0\n")).returncode != 0
    assert validate(b"not a tar archive").returncode != 0
    assert validate(json.dumps({"sha": "b" * 40}).encode(), "commit", "a" * 12).returncode != 0

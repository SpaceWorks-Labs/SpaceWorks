"""Archive checks remain active with a disposable loopback release provider."""
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tarfile

import pytest

ROOT = Path(__file__).resolve().parents[4]


@pytest.fixture
def fetch():
    spec = importlib.util.spec_from_file_location("release_fetch", ROOT / "scripts/installer/release-fetch.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def archive(tmp_path, entries):
    path = tmp_path / "release.tar.gz"
    blobs = []
    with tarfile.open(path, "w:gz") as bundle:
        for name, content, kind in entries:
            info = tarfile.TarInfo("release/" + name)
            info.type = kind
            info.size = len(content)
            info.mode = 0o755 if name.endswith(".sh") else 0o644
            bundle.addfile(info, io.BytesIO(content) if kind == tarfile.REGTYPE else None)
            blobs.append({"path": name, "type": "blob", "mode": "100755" if name.endswith(".sh") else "100644",
                          "size": len(content), "sha": hashlib.sha1(f"blob {len(content)}\0".encode() + content).hexdigest()})
    return path, {"truncated": False, "tree": blobs}


def test_exact_git_blobs_and_executable_modes_are_preserved(fetch, tmp_path):
    path, tree = archive(tmp_path, [("VERSION", b"0.9.2\n", tarfile.REGTYPE), ("setup.sh", b"#!/bin/bash\n", tarfile.REGTYPE)])
    output = tmp_path / "runtime"
    output.mkdir()
    fetch.extract_verified(path, output, tree, "0.9.2-main.2.bbbbbbbbbbbb")
    assert (output / "setup.sh").read_bytes() == b"#!/bin/bash\n"
    assert (output / "setup.sh").stat().st_mode & 0o111


@pytest.mark.parametrize("entries", [
    [("../escape", b"bad", tarfile.REGTYPE)], [("/absolute", b"bad", tarfile.REGTYPE)],
    [("link", b"", tarfile.SYMTYPE)], [("hard", b"", tarfile.LNKTYPE)],
    [("a", b"a", tarfile.REGTYPE), ("a", b"a", tarfile.REGTYPE)],
    [("C:escape", b"bad", tarfile.REGTYPE)], [("a\\b", b"bad", tarfile.REGTYPE)],
])
def test_unsafe_members_are_refused_before_execution(fetch, tmp_path, entries):
    path, tree = archive(tmp_path, entries)
    output = tmp_path / "runtime"
    output.mkdir()
    with pytest.raises((ValueError, FileExistsError)):
        fetch.extract_verified(path, output, tree, "0.9.2-main.2.bbbbbbbbbbbb")
    assert not (tmp_path / "escape").exists()


def test_modified_or_truncated_tree_cannot_authorize_archive(fetch, tmp_path):
    path, tree = archive(tmp_path, [("VERSION", b"0.9.2\n", tarfile.REGTYPE)])
    output = tmp_path / "runtime"
    output.mkdir()
    tree["tree"][0]["sha"] = "0" * 40
    with pytest.raises(ValueError, match="checksum"):
        fetch.extract_verified(path, output, tree, "0.9.2-main.2.bbbbbbbbbbbb")
    tree["truncated"] = True
    with pytest.raises(ValueError, match="Incomplete"):
        fetch.extract_verified(path, output, tree, "0.9.2-main.2.bbbbbbbbbbbb")


@pytest.mark.parametrize("origin,enabled", [("http://example.org:5000", "1"), ("http://127.0.0.1:5000", ""),
                                           ("http://user@127.0.0.1:5000", "1"), ("http://127.0.0.1:5000/path", "1")])
def test_release_fixture_override_requires_explicit_loopback_test_mode(fetch, monkeypatch, origin, enabled):
    monkeypatch.setenv("SPACEWORKS_INSTALL_TEST_API", origin)
    monkeypatch.setenv("SPACEWORKS_INSTALL_TEST_MODE", enabled)
    with pytest.raises(ValueError):
        fetch.mapped_url("https://api.github.com/repos/Owner/Repo/releases")


def test_fixture_does_not_bypass_blob_validation(fetch, monkeypatch):
    monkeypatch.setenv("SPACEWORKS_INSTALL_TEST_API", "http://127.0.0.1:5000")
    monkeypatch.setenv("SPACEWORKS_INSTALL_TEST_MODE", "1")
    assert fetch.mapped_url("https://github.com/Owner/Repo/archive/abc.tar.gz") == (
        "http://127.0.0.1:5000/github/Owner/Repo/archive/abc.tar.gz", "=http,https")


def test_nonpinned_selection_checks_repository(fetch):
    foreign = {"tag_name": "v0.9.2-main.2.bbbbbbbbbbbb", "draft": False, "prerelease": False,
               "published_at": "2026-10-18T00:00:00Z", "html_url": "https://github.com/Foreign/Repo/releases/tag/v0.9.2-main.2.bbbbbbbbbbbb"}
    with pytest.raises(ValueError):
        fetch.selector.select_release(json.dumps([foreign]), repository="Owner/Repo")

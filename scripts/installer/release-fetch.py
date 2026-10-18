#!/usr/bin/env python3
"""Fetch immutable GitHub release bytes and verify each member against its Git blob."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import sys
import subprocess
import tarfile
from urllib.parse import urlsplit

SCRIPTS = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("release_selector", SCRIPTS / "select-main-release.py")
selector = importlib.util.module_from_spec(spec)
spec.loader.exec_module(selector)


def mapped_url(url):
    fixture = os.environ.get("SPACEWORKS_INSTALL_TEST_API", "")
    if not fixture:
        if os.environ.get("SPACEWORKS_INSTALL_TEST_MODE"):
            raise ValueError("Test mode requires a loopback fixture provider.")
        return url, "=https"
    parsed = urlsplit(fixture)
    if (os.environ.get("SPACEWORKS_INSTALL_TEST_MODE") != "1" or parsed.hostname != "127.0.0.1"
            or parsed.scheme not in {"http", "https"} or not parsed.port
            or parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in {"", "/"}):
        raise ValueError("Release fixture override requires explicit test opt-in and a loopback origin.")
    prefixes = {"https://api.github.com/": "/api/", "https://raw.githubusercontent.com/": "/raw/",
                "https://github.com/": "/github/"}
    for prefix, replacement in prefixes.items():
        if url.startswith(prefix):
            return fixture.rstrip("/") + replacement + url[len(prefix):], "=http,https"
    raise ValueError("Unsupported fixture URL.")


def download(url, destination, limit, timeout=30):
    url, protocols = mapped_url(url)
    command = ["curl", "--fail", "--silent", "--show-error", "--location", "--proto", protocols,
               "--proto-redir", protocols, "--connect-timeout", "10", "--max-time", str(timeout),
               "--retry", "2", "--max-filesize", str(limit), "--header", "User-Agent: SpaceWorks-installer",
               "-o", str(destination), url]
    try:
        result = subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                timeout=3 * timeout + 60, check=False)
        if result.returncode or not destination.is_file() or destination.stat().st_size > limit:
            raise ValueError("Release provider returned an incomplete or oversized response.")
    except (OSError, subprocess.TimeoutExpired):
        destination.unlink(missing_ok=True)
        raise ValueError("Release provider is unavailable.") from None


def fetch_json(url, path):
    download(url, path, 8_000_000)
    return json.loads(path.read_text(encoding="utf-8"))


def extract_verified(archive_path, destination, tree, version):
    if tree.get("truncated") is not False:
        raise ValueError("Incomplete Git tree.")
    blobs = {entry["path"]: entry for entry in tree["tree"] if entry["type"] == "blob"}
    seen = set()
    root = None
    total = 0
    with tarfile.open(archive_path, "r:gz") as archive:
        for index, member in enumerate(archive):
            path = Path(member.name)
            total += member.size
            if (index >= 100_000 or total > 500_000_000 or member.size < 0
                    or not path.parts or path.is_absolute() or ".." in path.parts
                    or "\\" in member.name or ":" in member.name
                    or member.name.rstrip("/") != path.as_posix()
                    or not (member.isfile() or member.isdir())):
                raise ValueError("Unsafe or oversized source archive.")
            root = root or path.parts[0]
            if root != path.parts[0] or member.name in seen:
                raise ValueError("Duplicate or unrelated archive member.")
            seen.add(member.name)
            relative = "/".join(path.parts[1:])
            target = destination / relative
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            entry = blobs.get(relative, {})
            if entry.get("mode") not in {"100644", "100755"} or entry.get("size") != member.size:
                raise ValueError("Archive member differs from the selected Git tree.")
            target.parent.mkdir(parents=True, exist_ok=True)
            digest = hashlib.sha1(f"blob {member.size}\0".encode())
            with archive.extractfile(member) as source, target.open("xb") as output:
                while block := source.read(1024 * 1024):
                    digest.update(block)
                    output.write(block)
            if digest.hexdigest() != entry.get("sha"):
                raise ValueError("Archive Git blob checksum mismatch.")
            target.chmod(0o755 if entry["mode"] == "100755" else 0o644)
    if (destination / "VERSION").read_text().strip() != version.split("-main.")[0]:
        raise ValueError("Archive VERSION mismatch.")


def archive_digest(path):
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--version", default="")
    parser.add_argument("--destination", required=True, type=Path)
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9-]{0,38}/[A-Za-z0-9_.-]{1,100}", args.repository):
        raise ValueError("Invalid GitHub repository.")
    stage = args.destination
    stage.mkdir(mode=0o700, parents=True, exist_ok=True)
    base = f"https://api.github.com/repos/{args.repository}"
    endpoint = f"/releases/tags/v{args.version}" if args.version else "/releases?per_page=100"
    release = fetch_json(base + endpoint, stage / "release.json")
    version = selector.select_release(json.dumps(release), args.version, args.repository)
    commit = fetch_json(base + f"/commits/v{version}", stage / "commit.json")
    sha = commit.get("sha", "")
    if not re.fullmatch(r"[0-9a-f]{40}", sha) or not sha.startswith(version.rsplit(".", 1)[1]):
        raise ValueError("Release commit suffix mismatch.")
    tree = fetch_json(base + f"/git/trees/{sha}?recursive=1", stage / "tree.json")
    archive = stage / "release.tar.gz"
    download(f"https://github.com/{args.repository}/archive/{sha}.tar.gz", archive, 100_000_000, 300)
    runtime = stage / "runtime"
    runtime.mkdir(mode=0o700)
    extract_verified(archive, runtime, tree, version)
    metadata = {"schema_version": 1, "repository": args.repository, "release": version,
                "commit": sha, "archive_sha256": archive_digest(archive)}
    (runtime / ".spaceworks-release.json").write_text(json.dumps(metadata) + "\n")
    print(version)


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, KeyError, TypeError, tarfile.TarError, RecursionError):
        sys.exit("Release verification failed; the installation was not changed.")

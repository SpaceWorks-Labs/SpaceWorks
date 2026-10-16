#!/usr/bin/env python3
"""Validate a release commit or a GitHub source archive before host execution."""
import json
from pathlib import PurePosixPath
import re
import sys
import tarfile


def main():
    mode, expected = sys.argv[1:]
    if mode == "commit":
        payload = json.load(sys.stdin)
        commit = payload.get("sha", "") if isinstance(payload, dict) else ""
        if not re.fullmatch(r"[0-9a-f]{40}", commit) or not commit.startswith(expected):
            raise ValueError("Release tag does not match its immutable commit suffix.")
        print(commit)
        return
    if mode != "archive":
        raise ValueError("Unknown bundle validation mode.")
    found = set()
    root = None
    total = 0
    with tarfile.open(fileobj=sys.stdin.buffer, mode="r|gz") as archive:
        for index, member in enumerate(archive):
            path = PurePosixPath(member.name)
            total += member.size
            if (not path.parts or member.name.rstrip("/") != path.as_posix()
                    or index > 100_000 or total > 500_000_000 or path.is_absolute()
                    or ".." in path.parts or "\\" in member.name or ":" in member.name
                    or not (member.isfile() or member.isdir())):
                raise ValueError("Unsafe or oversized host archive.")
            root = root or path.parts[0]
            if path.parts[0] != root or member.name in found:
                raise ValueError("Archive has multiple roots or duplicate entries.")
            found.add(member.name)
            relative = "/".join(path.parts[1:])
            if relative == "VERSION":
                if (not member.isfile() or member.size > 100
                        or archive.extractfile(member).read().decode().strip() != expected):
                    raise ValueError("Host bundle VERSION does not match selected release.")
    for required in ("VERSION", "scripts/update.sh", "scripts/install-host-bundle.sh",
                     "scripts/update-release-bundle.sh", "scripts/release-host-bundle.py",
                     "docker-compose.prod.yml"):
        if f"{root}/{required}" not in found:
            raise ValueError(f"Incomplete release archive: {required}.")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, KeyError, TypeError, OSError, EOFError, tarfile.TarError, UnicodeError) as exc:
        sys.exit(f"Host bundle validation failed: {exc}")

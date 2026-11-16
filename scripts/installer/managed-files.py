#!/usr/bin/env python3
"""Seal the closed runtime inventory after successful fresh install or upgrade."""
import json
import os
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from state import atomic_write, digest


def main():
    root, metadata = map(Path, sys.argv[1:3])
    project = sys.argv[3]
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", project):
        raise ValueError("Invalid project identity.")
    root = root.absolute()
    if root.resolve() != root or not root.is_dir() or (root / ".git").exists():
        raise ValueError("Registration requires a dedicated installed release.")
    facts = json.loads(metadata.read_text())
    if (facts.get("schema_version") != 1 or not re.fullmatch(r"[0-9a-f]{64}", facts.get("archive_sha256", ""))
            or not re.fullmatch(r"[0-9a-f]{40}", facts.get("commit", ""))
            or not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+-main\.[0-9]+\.[0-9a-f]{12}", facts.get("release", ""))
            or not facts["commit"].startswith(facts["release"].rsplit(".", 1)[1])):
        raise ValueError("Invalid verified release metadata.")
    files = {}
    for relative in sys.stdin.read(100_001).splitlines():
        path = root / relative
        if (not relative or relative.startswith(".") or Path(relative).is_absolute()
                or ".." in Path(relative).parts or path.resolve() != path
                or not path.is_file() or path.stat().st_uid != root.stat().st_uid):
            raise ValueError("Invalid managed runtime inventory.")
        files[relative] = digest(path)
    if not files or "scripts/uninstall.sh" not in files or "install.sh" not in files:
        raise ValueError("Incomplete managed runtime inventory.")
    facts.update({"root": str(root), "owner": root.stat().st_uid, "phase": "complete", "files": files, "project": project})
    atomic_write(root / ".spaceworks-managed-files.json", facts)


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, KeyError, TypeError, IndexError):
        sys.exit("Cannot seal the installed runtime inventory; keep the verified release and private recovery state.")

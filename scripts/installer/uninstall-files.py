#!/usr/bin/env python3
"""Remove only recorded, unchanged runtime files; retain private recovery material."""
import hashlib
import json
import os
from pathlib import Path
import stat
import sys


def main():
    root = Path(sys.argv[1]).absolute()
    if root.resolve() != root or root == Path(root.anchor) or (root / ".git").exists():
        raise ValueError("Not a dedicated installed release.")
    marker = root / ".spaceworks-managed-files.json"
    if not marker.exists():
        marker = root / ".spaceworks-install.json"
    from private_files import check_private
    check_private(marker)
    record = json.loads(marker.read_text())
    if (record.get("schema_version") != 1 or record.get("root") != str(root) or record.get("phase") != "complete"
            or record.get("owner") != root.stat().st_uid
            or record.get("release") != (root / ".spaceworks-version").read_text().strip()):
        raise ValueError("No completed installation record.")
    paths = sys.stdin.read().splitlines()
    removals = []
    for relative in paths:
        file = root / relative
        if Path(relative).is_absolute() or ".." in Path(relative).parts or relative.startswith("."):
            raise ValueError("Invalid managed file.")
        if file.resolve().parent != file.parent.resolve() or file.is_symlink():
            raise ValueError("Managed file is a symlink.")
        # No ancestor may redirect removal outside the dedicated install root.
        if any(parent.is_symlink() for parent in file.parents if parent != root.parent):
            raise ValueError("Managed file ancestor is a symlink.")
        expected = record["files"].get(relative)
        if file.is_file() and expected:
            with file.open("rb") as handle:
                digest = hashlib.sha256()
                for block in iter(lambda: handle.read(1024 * 1024), b""):
                    digest.update(block)
                if digest.hexdigest() == expected:
                    removals.append(file)
    # Validate the complete list before deleting any managed file.
    if "--validate" in sys.argv[2:]:
        return
    for file in removals:
        file.unlink()
    print(f"Removed {len(removals)} unchanged recorded runtime files; modified files and private data retained.")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, KeyError, TypeError):
        sys.exit("Uninstall refused unverified file ownership; private installation state was retained.")

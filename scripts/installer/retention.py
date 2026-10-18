#!/usr/bin/env python3
"""Bound completed update backups; never traverse symlinks or restore workspaces."""
import argparse
import os
from pathlib import Path
import re
import stat
import sys
import time

NAME = re.compile(r"(?:pre-update-[0-9TZ-]+\.sql\.gz|host-config-[0-9TZ-]+|\.env\.pre-restore-[0-9TZ-]+)")


def remove_owned(path, owner, cutoff):
    info = path.lstat()
    if info.st_uid != owner or info.st_mtime >= cutoff or stat.S_ISLNK(info.st_mode):
        return
    if stat.S_ISREG(info.st_mode):
        path.unlink()
    elif stat.S_ISDIR(info.st_mode):
        # Inspect the entire tree before deleting any of it.
        children = list(path.rglob("*"))
        for child in children:
            child_info = child.lstat()
            if (child_info.st_uid != owner or stat.S_ISLNK(child_info.st_mode)
                    or not (stat.S_ISREG(child_info.st_mode) or stat.S_ISDIR(child_info.st_mode))):
                raise ValueError("Unsafe backup tree; retention stopped.")
        for child in sorted(children, key=lambda item: len(item.parts), reverse=True):
            child.rmdir() if child.is_dir() else child.unlink()
        path.rmdir()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--days", type=int, default=14)
    parser.add_argument("--exclude", action="append", default=[], type=Path)
    args = parser.parse_args()
    root = args.root.absolute()
    if root.resolve() != root or not 1 <= args.days <= 365:
        raise ValueError("Invalid retention root/window.")
    if (root / ".spaceworks-import-pending.json").exists() or (root / ".spaceworks-transition.json").exists():
        return  # ambiguous operation material is never ordinary retention
    cutoff = time.time() - args.days * 86400
    owner = root.stat().st_uid
    for directory in (root, root / "backups"):
        if directory.is_symlink() or not directory.is_dir():
            continue
        for child in directory.iterdir():
            if NAME.fullmatch(child.name) and child.absolute() not in args.exclude:
                remove_owned(child, owner, cutoff)


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError):
        sys.exit("Private backup retention refused unsafe or unreadable state; files were retained.")

#!/usr/bin/env python3
"""Private terminal receipts: age alone never authorizes deleting recovery material."""
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
import time
import uuid

BACKUP = re.compile(r"(?:backups/(?:pre-update-[0-9TZ-]+\.(?:sql\.gz|dump)|host-config-[0-9TZ-]+|pre-h1-[0-9TZ-]+\.dump(?:\.env)?)|\.env\.pre-restore-[0-9TZ-]+|(?:work/)?restore-[0-9a-f-]{36})")


def check_private(path, owner, private=True, runtime=False):
    info = path.lstat()
    owners = {owner, 0, 10001} if runtime else {owner, 0}
    if (info.st_uid not in owners or stat.S_ISLNK(info.st_mode)
            or not (stat.S_ISREG(info.st_mode) or stat.S_ISDIR(info.st_mode))
            or (stat.S_ISREG(info.st_mode) and info.st_nlink != 1)
            or (private and os.name != "nt" and info.st_mode & 0o077)):
        raise ValueError("Unsafe private recovery material.")
    return info


def fingerprint(path, owner):
    """Bind a receipt to exact bytes and tree names; never follow redirected children."""
    digest = hashlib.sha256()
    check_private(path, owner, runtime=True)
    def visit(current):
        info = check_private(current, owner, private=False, runtime=True)
        relative = current.relative_to(path).as_posix()
        digest.update(json.dumps([relative, stat.S_ISDIR(info.st_mode)]).encode() + b"\0")
        if stat.S_ISDIR(info.st_mode):
            for child in sorted(current.iterdir()):
                visit(child)
        else:
            with current.open("rb") as handle:
                for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                    digest.update(chunk)
    visit(path)
    return digest.hexdigest()


def sync_directory(directory):
    if os.name == "nt":
        return
    descriptor = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def seal(root, paths, outcome):
    root = root.absolute()
    if root.resolve() != root or outcome not in {"updated", "transitioned", "restored", "rolled_back", "aborted"}:
        raise ValueError("Invalid terminal recovery receipt.")
    owner = root.stat().st_uid
    entries = {}
    for path in paths:
        path = path.absolute()
        relative = path.relative_to(root).as_posix()
        if path.resolve() != path or not BACKUP.fullmatch(relative):
            raise ValueError("Unowned retention path.")
        entries[relative] = fingerprint(path, owner)
    if not entries:
        raise ValueError("Empty terminal receipt.")
    directory = root / ".spaceworks-retention"
    directory.mkdir(mode=0o700, exist_ok=True)
    check_private(directory, owner)
    receipt = directory / (uuid.uuid4().hex + ".json")
    descriptor = os.open(receipt, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        json.dump({"schema_version": 1, "completed_at": time.time(), "outcome": outcome,
                   "entries": entries}, handle, sort_keys=True)
        handle.flush()
        os.fsync(handle.fileno())
    sync_directory(directory)


if __name__ == "__main__":
    try:
        root, outcome, *paths = sys.argv[1:]
        seal(Path(root), list(map(Path, paths)), outcome)
    except (OSError, ValueError):
        sys.exit("Cannot seal terminal recovery receipt; private material retained without automatic expiry.")

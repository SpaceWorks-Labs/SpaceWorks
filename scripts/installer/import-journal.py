#!/usr/bin/env python3
"""Durable continuity intent; a retry repairs exact pre-effect state before Compose."""
import json
import os
from pathlib import Path
import re
import stat
import sys


def sync_parent(path):
    descriptor = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def load_journal(journal, root, ops):
    info = journal.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_mode & 0o077 or info.st_uid != os.getuid():
        raise ValueError("Unsafe continuity journal.")
    value = json.loads(journal.read_text())
    if (value.get("schema_version") != 1 or not re.fullmatch(r"import-[A-Za-z0-9]+", value["work"])
            or not re.fullmatch(r"\.env\.pre-restore-[0-9TZ-]+", value["backup"])
            or not re.fullmatch(r"sha256:[0-9a-f]{64}", value["image"])
            or value.get("phase", "configuration") not in {"configuration", "restore_registration"}):
        raise ValueError("Invalid continuity journal.")
    if "restore_id" in value and not re.fullmatch(r"[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}", value["restore_id"]):
        raise ValueError("Invalid restore identity.")
    work, backup = ops / "work" / value["work"], root / value["backup"]
    if work.is_symlink() or not work.is_dir() or backup.is_symlink() or not backup.is_file():
        raise ValueError("Missing continuity rollback material.")
    return value, work


def main():
    action, root, ops = sys.argv[1:4]
    root, ops = Path(root), Path(ops)
    journal = root / ".spaceworks-import-pending.json"
    if action == "begin":
        work, backup, image = sys.argv[4:]
        for path in (root / backup, Path(work) / "records.json"):
            if path.is_symlink() or not path.is_file():
                raise ValueError("Unsafe rollback material.")
            with path.open("rb") as handle:
                os.fsync(handle.fileno())
            sync_parent(path)
        value = {"schema_version": 1, "work": Path(work).name, "backup": backup, "image": image,
                 "phase": "configuration"}
        descriptor = os.open(journal, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(value, handle)
            handle.flush(); os.fsync(handle.fileno())
    elif action == "read":
        value, work = load_journal(journal, root, ops)
        if value.get("phase") == "restore_registration":
            restore = value.get("restore_id", "unknown")
            sys.exit(f"Restore registration may have committed (restore {restore}). Keep writers stopped; inspect the restore intent and supervised restore journal before recovering keys. Environment-only rollback is refused.")
        for item in (str(work), value["backup"], value["image"]):
            sys.stdout.buffer.write(item.encode() + b"\0")
    elif action in {"seal", "registered"}:
        value, _ = load_journal(journal, root, ops)
        value["phase"] = "restore_registration"
        if action == "registered":
            restore = sys.argv[4].lower()
            if not re.fullmatch(r"[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}", restore):
                raise ValueError("Invalid restore identity.")
            value["restore_id"] = restore
        temporary = journal.with_suffix(".new")
        descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(value, handle)
            handle.flush(); os.fsync(handle.fileno())
        temporary.replace(journal)
    elif action == "clear":
        load_journal(journal, root, ops)
        temporary = journal.with_suffix(".new")
        if temporary.exists() or temporary.is_symlink():
            info = temporary.lstat()
            if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
                raise ValueError("Unsafe continuity checkpoint.")
            temporary.unlink()
        journal.unlink()
    else:
        raise ValueError("Unknown continuity journal action.")
    sync_parent(journal)


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, KeyError, IndexError, TypeError):
        sys.exit("Continuity recovery journal is unsafe or incomplete; leave writers stopped and recover its private snapshot.")

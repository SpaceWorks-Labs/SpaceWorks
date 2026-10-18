#!/usr/bin/env python3
"""Expire proven terminal recovery batches after 14 days; retain uncertain work."""
import argparse
import os
from pathlib import Path
import re
import stat
import sys
import time
import importlib.util
import json
import math

spec = importlib.util.spec_from_file_location("retention_receipts", Path(__file__).with_name("retention-receipts.py"))
receipts = importlib.util.module_from_spec(spec)
spec.loader.exec_module(receipts)

def remove_owned(path, owner, cutoff):
    info = path.lstat()
    if info.st_uid not in {owner, 0} or info.st_mtime >= cutoff or stat.S_ISLNK(info.st_mode):
        return
    if stat.S_ISREG(info.st_mode):
        path.unlink()
    elif stat.S_ISDIR(info.st_mode):
        # Inspect the entire tree before deleting any of it.
        children = list(path.rglob("*"))
        for child in children:
            child_info = child.lstat()
            if (child_info.st_uid not in {owner, 0} or stat.S_ISLNK(child_info.st_mode)
                    or not (stat.S_ISREG(child_info.st_mode) or stat.S_ISDIR(child_info.st_mode))):
                raise ValueError("Unsafe backup tree; retention stopped.")
        for child in sorted(children, key=lambda item: len(item.parts), reverse=True):
            child.rmdir() if child.is_dir() else child.unlink()
        path.rmdir()


def expire(root, days=14, excluded=(), now=None):
    root = root.absolute()
    if root.resolve() != root or not 14 <= days <= 365:
        raise ValueError("Invalid retention root/window.")
    if any((root / name).exists() or (root / name).is_symlink() for name in
           (".spaceworks-import-pending.json", ".spaceworks-transition.json")):
        return
    directory = root / ".spaceworks-retention"
    if not directory.exists():
        return  # Legacy/unreceipted material is never guessed safe.
    owner = root.stat().st_uid
    receipts.check_private(directory, owner)
    cutoff = (time.time() if now is None else now) - days * 86400
    batches = []
    for receipt in sorted(directory.iterdir()):
        receipts.check_private(receipt, owner)
        if not re.fullmatch(r"[0-9a-f]{32}\.json", receipt.name):
            raise ValueError("Unknown recovery receipt.")
        value = json.loads(receipt.read_text(encoding="utf-8"))
        if (value.get("schema_version") != 1 or not isinstance(value.get("completed_at"), (int, float))
                or not math.isfinite(value["completed_at"]) or value["completed_at"] <= 0
                or value.get("outcome") not in {"updated", "transitioned", "restored", "rolled_back", "aborted"}
                or not isinstance(value.get("entries"), dict) or not value["entries"]):
            raise ValueError("Invalid recovery receipt.")
        paths = []
        for relative, digest in value["entries"].items():
            if not receipts.BACKUP.fullmatch(relative) or not re.fullmatch(r"[0-9a-f]{64}", digest):
                raise ValueError("Unowned recovery receipt path.")
            path = root / relative
            if path.resolve() != path:
                raise ValueError("Redirected recovery path.")
            paths.append(path)
        batches.append((value["completed_at"], receipt, value, paths))
    # Always keep the newest batch of each recovery family, even if very old.
    latest, newest_path = {}, {}
    def family(path):
        name = path.name
        return next(prefix for prefix in ("pre-update", "host-config", "pre-h1", ".env.pre-restore", "restore-") if name.startswith(prefix))
    for at, receipt, value, paths in sorted(batches, key=lambda row: (row[0], row[1].name)):
        for path in paths:
            latest[family(path)] = receipt
            newest_path[path] = receipt
    excluded = {Path(path).absolute() for path in excluded}
    for at, receipt, value, paths in batches:
        if all(newest_path[path] != receipt for path in paths):
            # A retried terminal cleanup may reseal the same workspace. Supersede
            # the old receipt, never delete a newer receipt's recovery material.
            receipt.unlink()
            receipts.sync_directory(directory)
            continue
        if any(newest_path[path] != receipt for path in paths):
            continue
        if at >= cutoff or any(path in excluded or latest[family(path)] == receipt for path in paths):
            continue
        # All entries are checked before any removal. A changed batch stays protected.
        present = [path for path in paths if path.exists() or path.is_symlink()]
        if any(receipts.fingerprint(path, owner) != value["entries"][path.relative_to(root).as_posix()] for path in present):
            continue
        for path in present:
            # Receipt time, not the copied file's old mtime, governs retention.
            remove_owned(path, path.lstat().st_uid, float("inf"))
        receipt.unlink()
        receipts.sync_directory(directory)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--days", type=int, default=14)
    parser.add_argument("--exclude", action="append", default=[], type=Path)
    args = parser.parse_args()
    expire(args.root, args.days, args.exclude)


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError):
        sys.exit("Private backup retention refused unsafe or unreadable state; files were retained.")

#!/usr/bin/env python3
"""Snapshot/restore topology bytes and POSIX metadata using pinned root tooling."""
import base64
import json
import os
from pathlib import Path
import re
import stat
import sys

NAME = re.compile(r"compose-topology(?:-[a-z-]+)?\.json")


def records(directory):
    result = {}
    for path in directory.glob("compose-topology*.json"):
        info = path.lstat()
        if not NAME.fullmatch(path.name) or not stat.S_ISREG(info.st_mode):
            raise ValueError("Unsafe topology record.")
        result[path.name] = path
    return result


def main():
    action, ops, snapshot = sys.argv[1:]
    ops, snapshot = Path(ops), Path(snapshot)
    if ops.is_symlink() or snapshot.is_symlink() or os.geteuid() != 0:
        raise ValueError("Root-owned snapshot tooling is required.")
    current = records(ops)
    if action == "snapshot":
        value = {}
        for name, path in current.items():
            info = path.stat()
            value[name] = {"bytes": base64.b64encode(path.read_bytes()).decode(),
                           "uid": info.st_uid, "gid": info.st_gid, "mode": stat.S_IMODE(info.st_mode),
                           "atime_ns": info.st_atime_ns, "mtime_ns": info.st_mtime_ns}
        with snapshot.open("x", encoding="utf-8") as handle:
            os.chmod(snapshot, 0o600)
            json.dump(value, handle)
            handle.flush(); os.fsync(handle.fileno())
        parent = os.open(snapshot.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(parent)
        finally:
            os.close(parent)
    elif action == "restore":
        info = snapshot.lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or stat.S_IMODE(info.st_mode) != 0o600 or info.st_nlink != 1:
            raise ValueError("Snapshot is not the root-owned private record.")
        value = json.loads(snapshot.read_text())
        if any(not NAME.fullmatch(name) for name in value):
            raise ValueError("Unknown snapshot member.")
        # Validate all metadata before changing any record.
        decoded = {}
        for name, entry in value.items():
            decoded[name] = base64.b64decode(entry["bytes"], validate=True)
            if not all(type(entry[key]) is int and entry[key] >= 0 for key in ("uid", "gid", "mode", "atime_ns", "mtime_ns")):
                raise ValueError("Invalid record metadata.")
        for name, raw in decoded.items():
            entry = value[name]
            path = ops / name
            temporary = path.with_suffix(".restore-new")
            descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(raw); handle.flush()
                os.fchown(handle.fileno(), entry["uid"], entry["gid"])
                os.fchmod(handle.fileno(), entry["mode"])
                os.fsync(handle.fileno())
            os.utime(temporary, ns=(entry["atime_ns"], entry["mtime_ns"]))
            os.replace(temporary, path)
        for name, path in current.items():
            if name not in decoded:
                path.unlink()
    else:
        raise ValueError("Unknown snapshot action.")
    descriptor = os.open(ops, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, KeyError, TypeError):
        sys.exit("Topology snapshot operation failed; keep writers stopped until private recovery completes.")

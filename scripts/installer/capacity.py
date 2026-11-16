#!/usr/bin/env python3
"""Measure peak copies and aggregate allocations sharing a filesystem."""
import argparse
import json
from pathlib import Path, PurePosixPath
import shutil
import sys
import tarfile

GIB = 1024 ** 3


def archive_size(path):
    total, count = 0, 0
    with tarfile.open(path, mode="r:") as archive:
        for member in archive:
            count += 1
            name = PurePosixPath(member.name)
            if (name.is_absolute() or ".." in name.parts or "\\" in member.name
                    or not (member.isfile() or member.isdir()) or member.size < 0
                    or count > 1_000_000):
                raise ValueError("Unsafe or excessive restore archive.")
            total += member.size + 4096  # filesystem blocks and per-entry overhead
            if total > 1024 * GIB:
                raise ValueError("Restore archive exceeds supervised capacity envelope.")
    return total


def ancestor(path):
    # This is a read-only capacity query, including legitimate OS temp symlinks
    # (macOS /var -> /private/var); destructive path checks remain separate.
    path = Path(path).absolute().resolve()
    while not path.exists():
        path = path.parent
    return path


def admit(allocations, disk_usage=shutil.disk_usage):
    devices = {}
    for path, size in allocations:
        if not isinstance(size, int) or size < 0:
            raise ValueError("Invalid capacity estimate.")
        existing = ancestor(path)
        device = existing.stat().st_dev
        prior, amount = devices.get(device, (existing, 0))
        devices[device] = prior, amount + size
    for path, required in devices.values():
        if disk_usage(path).free < required:
            raise ValueError("Insufficient peak capacity.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=("upgrade", "import", "restore"), required=True)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--docker-root", type=Path, required=True)
    parser.add_argument("--docker-free", type=int, required=True)
    parser.add_argument("--docker-separate", action="store_true")
    parser.add_argument("--temp", type=Path, required=True)
    parser.add_argument("--source", type=Path)
    parser.add_argument("--plain", type=Path)
    args = parser.parse_args()
    metrics = json.load(sys.stdin)
    database, media = metrics["database_bytes"], metrics["object_bytes"]
    if any(type(value) is not int or not 0 <= value <= 1024 * GIB for value in (database, media)):
        raise ValueError("Invalid measured deployment size.")
    archive_bytes = metrics.get("archive_bytes", 0)
    if type(archive_bytes) is not int or not 0 <= archive_bytes <= 1024 * GIB:
        raise ValueError("Invalid archive size measurement.")
    encrypted = max(args.source.stat().st_size if args.source else 0, archive_bytes)
    extracted = archive_size(args.plain) if args.plain else encrypted * 2
    # DB may coexist as live, diff sibling and pre-restore snapshot. Replacement
    # objects need both old rollback and new bytes, even on a nonversioned store.
    docker_required = database * 3 + media * 2 + 8 * GIB
    if args.docker_free < docker_required:
        raise ValueError("Insufficient Docker data filesystem capacity.")
    allocations = [(args.root / "backups", database * 2 + GIB),
                   (args.root if args.docker_separate else args.docker_root, docker_required),
                   (args.temp, database + GIB),
                   (args.work, encrypted * 2 + extracted * 2 + database * 2 + media)]
    admit(allocations)


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, KeyError, tarfile.TarError, TypeError):
        sys.exit("Peak capacity admission failed; private recovery material retained. Free space or relocate configured state before retrying.")

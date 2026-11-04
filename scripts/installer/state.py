#!/usr/bin/env python3
"""Private install journal: validate interrupted work before trusting saved answers."""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
import tempfile

MARKER = ".spaceworks-install.json"
PHASES = ("copying", "copied", "environment", "services", "configured", "complete")


def digest(path):
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def private_file(path):
    from private_files import check_private
    return check_private(path)


def atomic_write(path, value):
    temporary = path.with_suffix(".new")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        from private_files import make_private
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            make_private(temporary)
            json.dump(value, handle, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        if os.name != "nt":
            descriptor = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
    finally:
        temporary.unlink(missing_ok=True)


def validate(root, repository, release, check_private=True):
    path = root / MARKER
    private_file(path)
    value = json.loads(path.read_text(encoding="utf-8"))
    if (value.get("schema_version") != 1 or value.get("root") != str(root)
            or value.get("repository") != repository or value.get("release") != release
            or value.get("phase") not in PHASES):
        raise ValueError("Incomplete install identity differs; restore its pinned release before retrying.")
    for relative, expected in value["files"].items():
        file = root / relative
        if value["phase"] == "copying" and not file.exists() and not file.is_symlink():
            continue
        if (not relative or Path(relative).is_absolute() or ".." in Path(relative).parts
                or file.is_symlink() or not file.is_file() or digest(file) != expected):
            raise ValueError("Incomplete install runtime was changed; refusing to overwrite it.")
    if value.get("owner") != root.stat().st_uid:
        raise ValueError("Install owner changed.")
    for name, expected in (value.get("private", {}) if check_private else {}).items():
        if name not in {".env", ".spaceworks-answers", ".spaceworks-layer"}:
            raise ValueError("Unknown private install artifact.")
        file = root / name
        if value["phase"] == "copying" and not file.exists() and not file.is_symlink():
            continue
        if name != ".spaceworks-layer":
            private_file(file)
        if file.is_symlink() or digest(file) != expected:
            raise ValueError("Incomplete install settings changed; inspect private recovery state.")
    if value["phase"] == "copying" and (root / ".env").exists():
        raise ValueError("An environment was created before the owned copy completed.")
    return value


def restore_answers(root, value):
    target = root / ".spaceworks-answers"
    if target.exists() or value["phase"] != "copying" or not value.get("answers_b64"):
        return
    raw = base64.b64decode(value["answers_b64"], validate=True)
    if hashlib.sha256(raw).hexdigest() != value["private"][".spaceworks-answers"]:
        raise ValueError("Saved answer recovery digest differs.")
    from private_files import make_private
    descriptor, name = tempfile.mkstemp(prefix=".answers-restore-", dir=root)
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            make_private(temporary)
            handle.write(raw); handle.flush(); os.fsync(handle.fileno())
        if target.exists() or target.is_symlink():
            raise ValueError("Answers appeared during recovery; refusing overwrite.")
        os.replace(temporary, target)
        if os.name != "nt":
            parent = os.open(root, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(parent)
            finally:
                os.close(parent)
    finally:
        temporary.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "create", "validate", "phase", "status", "restore-answers", "validate-source"))
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--release", required=True)
    parser.add_argument("--source", type=Path)
    parser.add_argument("--phase", choices=PHASES, default="copied")
    args = parser.parse_args()
    root = args.root.absolute()
    if root.is_symlink() or root.resolve() != root or not root.is_dir():
        raise ValueError("Install root must be a canonical directory.")
    if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+-main\.[0-9]+\.[0-9a-f]{12}", args.release):
        raise ValueError("Install journal requires a pinned main release.")
    if args.action in {"prepare", "create"}:
        source = args.source if args.action == "prepare" else root
        if source is None:
            raise ValueError("Prepare requires the verified source directory.")
        if (root / MARKER).exists():
            raise ValueError("Install journal already exists.")
        files = {}
        for file in source.rglob("*"):
            relative = file.relative_to(source).as_posix()
            if relative in {MARKER, ".spaceworks-answers", ".env"}:
                continue
            if file.is_symlink():
                raise ValueError("Install source contains a symlink.")
            if file.is_file():
                files[relative] = digest(file)
        value = {"schema_version": 1, "root": str(root), "repository": args.repository,
                 "release": args.release, "commit_suffix": args.release.rsplit(".", 1)[1],
                 "owner": root.stat().st_uid, "files": files, "phase": "copying" if args.action == "prepare" else "copied"}
        metadata = json.loads((source / ".spaceworks-release.json").read_text())
        if (metadata.get("schema_version") != 1 or metadata.get("release") != args.release or metadata.get("repository") != args.repository
                or not re.fullmatch(r"[0-9a-f]{40}", metadata.get("commit", ""))
                or not metadata["commit"].startswith(value["commit_suffix"])
                or not re.fullmatch(r"[0-9a-f]{64}", metadata.get("archive_sha256", ""))):
            raise ValueError("Verified source metadata is missing or differs.")
        value.update({key: metadata[key] for key in ("commit", "archive_sha256")})
        value["private"] = {name: digest(source / name) for name in
                            (".env", ".spaceworks-answers", ".spaceworks-layer") if (source / name).is_file()}
        if (source / ".spaceworks-answers").is_file():
            value["answers_b64"] = base64.b64encode((source / ".spaceworks-answers").read_bytes()).decode()
    else:
        value = validate(root, args.repository, args.release, check_private=args.action in {"validate", "status", "restore-answers", "validate-source"})
    if args.action == "status":
        print(value["phase"])
    elif args.action == "restore-answers":
        restore_answers(root, value)
    elif args.action == "validate-source":
        if args.source is None:
            raise ValueError("Missing verified source.")
        for name, expected in value["files"].items():
            candidate = args.source / name
            if candidate.is_symlink() or not candidate.is_file() or digest(candidate) != expected:
                raise ValueError("Resume requires the exact verified release bytes.")
    elif args.action in {"prepare", "create", "phase"}:
        if args.action == "phase":
            value["phase"] = args.phase
            value["private"] = {name: digest(root / name) for name in
                                (".env", ".spaceworks-answers", ".spaceworks-layer") if (root / name).is_file()}
        if value["phase"] == "complete":
            value.pop("answers_b64", None)
        atomic_write(root / MARKER, value)


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, KeyError, TypeError):
        sys.exit("Install journal validation failed; keep the private state and retry the exact release as its owner.")

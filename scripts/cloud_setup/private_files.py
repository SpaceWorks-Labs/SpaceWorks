"""Owned, private, atomic setup state; refuse links and concurrent invocations."""

from contextlib import contextmanager
import json
import os
from pathlib import Path
import stat
import tempfile

from .errors import SetupError

MAX_JSON_BYTES = 1024 * 1024


def no_links(path):
    path = Path(os.path.abspath(path))
    for part in (path, *path.parents):
        if part.is_symlink() or (hasattr(part, "is_junction") and part.is_junction()):
            raise SetupError("unsafe_path", "Use an owned path without symlinks or junctions.")
    return path


def check_private(path, *, directory=False, secret_mount=False):
    path = no_links(path)
    info = path.stat(follow_symlinks=False)
    expected = stat.S_ISDIR if directory else stat.S_ISREG
    if not expected(info.st_mode):
        raise SetupError("unsafe_file", "Use a regular private file or directory.")
    # Managed one-off jobs/local tooling require POSIX permission guarantees. Windows
    # chmod does not enforce 0600: refuse rather than claim ACLs have been checked.
    if os.name == "nt":
        raise SetupError("posix_permissions_required", "Run managed secret setup in a Linux one-off job or container.")
    trusted_mount = secret_mount and info.st_uid == 0 and info.st_gid == os.getegid() and not info.st_mode & 0o037
    if not trusted_mount and (info.st_uid != os.geteuid() or info.st_mode & 0o077):
        raise SetupError("unsafe_permissions", "Set owned files to 0600 and setup directories to 0700.")
    return path


def private_directory(path):
    path = no_links(path)
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    return check_private(path, directory=True)


def read_json(path, *, secret_mount=False):
    path = check_private(path, secret_mount=secret_mount)
    if path.stat().st_size > MAX_JSON_BYTES:
        raise SetupError("input_too_large", "Keep each setup JSON file below 1 MiB.")
    try:
        def unique(pairs):
            value = {}
            for key, item in pairs:
                if key in value:
                    raise ValueError("duplicate")
                value[key] = item
            return value
        value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique)
    except (ValueError, UnicodeError):
        raise SetupError("invalid_json", "Supply UTF-8 JSON with unique keys.") from None
    if not isinstance(value, dict):
        raise SetupError("invalid_json", "Supply a versioned JSON object.")
    return value


def sync_directory(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def write_private(path, payload):
    path = no_links(path)
    private_directory(path.parent)
    if path.exists():
        check_private(path)
    fd, temporary = tempfile.mkstemp(prefix=".setup-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        sync_directory(path.parent)
    finally:
        Path(temporary).unlink(missing_ok=True)


def write_json(path, value):
    write_private(path, json.dumps(value, indent=2, sort_keys=True) + "\n")


@contextmanager
def setup_lock(directory):
    path = private_directory(directory) / "setup.lock"
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        raise SetupError("setup_locked", "Another setup owns this directory; prove it stopped before removing setup.lock.") from None
    try:
        os.write(fd, str(os.getpid()).encode("ascii"))
        os.fsync(fd)
        yield
    finally:
        os.close(fd)
        path.unlink()
        sync_directory(path.parent)

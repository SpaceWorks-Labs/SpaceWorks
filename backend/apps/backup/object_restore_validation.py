"""Archive object-key validation shared through the original restore import path."""
from pathlib import PurePosixPath

from .object_restore_versions import ObjectRestoreError


def safe_restore_key(value):
    path = PurePosixPath(str(value))
    if path.is_absolute() or not path.parts or ".." in path.parts:
        raise ObjectRestoreError("Archive contains an unsafe object key.")
    return path.as_posix()

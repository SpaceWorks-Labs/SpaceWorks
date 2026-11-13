"""Explicit managed provider file delivery; imported before Django by lane M."""

import base64
import json
from pathlib import Path, PurePosixPath

from .errors import SetupError
from .private_files import read_json, write_private

INLINE_FILES = {
    "EMAIL_PROVIDER_CONFIG_FILE": "SPACEWORKS_EMAIL_PROVIDER_CONFIG_B64",
    "STORAGE_CAPABILITIES_FILE": "SPACEWORKS_STORAGE_CAPABILITIES_B64",
}


def read_config(values, name):
    inline = values.get(INLINE_FILES[name])
    if not inline:
        return read_json(values[name], secret_mount=True)
    try:
        if len(inline) > 131072:
            raise ValueError
        value = json.loads(base64.b64decode(inline, validate=True))
        if not isinstance(value, dict):
            raise ValueError
        return value
    except (ValueError, UnicodeError):
        raise SetupError("inline_secret_file_invalid", "Supply bounded base64-encoded JSON through the provider secret store; never via argv.") from None


def materialize_secret_files(environ):
    if environ.get("SPACEWORKS_SECRET_FILE_MODE", "native") != "inline":
        return
    selected = [(name, inline) for name, inline in INLINE_FILES.items() if environ.get(inline)]
    if not selected:
        return
    if environ.get("SPACEWORKS_DEPLOYMENT_MODE") != "managed":
        raise SetupError("inline_files_managed_only", "Inline provider files are explicit managed setup only; host startup stays unchanged.")
    for name, inline in selected:
        value = read_config(environ, name)
        target = PurePosixPath(environ.get(name, ""))
        if not target.is_absolute() or ".." in target.parts:
            raise SetupError("inline_secret_path", "Choose an absolute owned private secret path without parent traversal.")
        if not str(target).startswith("/tmp/spaceworks-secrets/"):
            raise SetupError("inline_secret_path", "Use /tmp/spaceworks-secrets/ for managed inline files, with an owned 0700 directory and 0600 files.")
        # write_private enforces no links, owned 0700 directory and 0600 file.
        write_private(Path(str(target)), json.dumps(value, separators=(",", ":")) + "\n")
        environ.pop(inline, None)

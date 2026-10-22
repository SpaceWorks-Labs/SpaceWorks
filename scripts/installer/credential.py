#!/usr/bin/env python3
"""Persist a generated credential privately, without stdout or secret argv."""
import json
import os
from pathlib import Path
import stat
import sys


def main():
    path = Path(sys.argv[1])
    value = {"username": os.environ["SETUP_BOOTSTRAP_USER"],
             "password": os.environ["SETUP_BOOTSTRAP_PASSWORD"], "must_change_password": True}
    from private_files import check_private, make_private
    if path.exists() or path.is_symlink():
        check_private(path)
        if json.loads(path.read_text()) != value:
            raise ValueError("Bootstrap credential file differs or is unsafe.")
        return
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        make_private(path)
        json.dump(value, handle)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, KeyError):
        sys.exit("Cannot safely save the private bootstrap credential; account setup was not started.")

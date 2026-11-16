#!/usr/bin/env python3
"""Install/remove only the exact daily systemd timer belonging to this install."""
import hashlib
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import stat


def quote(value):
    # systemd specifier and ExecStart environment expansion are distinct from sh.
    return '"' + str(value).replace('\\', '\\\\').replace('"', '\\"').replace('%', '%%').replace('$', '$$') + '"'


def units(root):
    name = "spaceworks-retention-" + hashlib.sha256(str(root).encode()).hexdigest()[:16]
    service = ("[Unit]\nDescription=Space Works private recovery retention\nAfter=docker.service\n"
               "[Service]\nType=oneshot\nUMask=0077\n"
               f"ExecStart=/bin/bash {quote(root / 'scripts/installer/retention-run.sh')}\n")
    timer = ("[Unit]\nDescription=Space Works daily private recovery retention\n"
             "[Timer]\nOnCalendar=daily\nPersistent=true\nRandomizedDelaySec=900\n"
             f"Unit={name}.service\n[Install]\nWantedBy=timers.target\n")
    return name, {name + ".service": service, name + ".timer": timer}


def apply(root, directory, action, run=subprocess.run):
    if (root.resolve() != root or root == Path(root.anchor)
            or any(ord(char) < 32 or ord(char) == 127 for char in str(root))
            or directory.resolve() != directory or not directory.is_dir()):
        raise ValueError("Noncanonical maintenance paths.")
    name, payloads = units(root)
    for filename, payload in payloads.items():
        target = directory / filename
        if target.is_symlink() or (target.exists() and target.read_text() != payload):
            raise ValueError("Foreign or modified maintenance unit; retained.")
        if target.exists():
            info = target.stat()
            if (not stat.S_ISREG(info.st_mode) or info.st_uid != directory.stat().st_uid
                    or info.st_nlink != 1 or (os.name != "nt" and info.st_mode & 0o022)):
                raise ValueError("Unsafe maintenance unit ownership.")
    if action == "remove":
        if not any((directory / filename).exists() for filename in payloads):
            return
        run(["systemctl", "disable", "--now", name + ".timer"], check=True,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30)
        # Uninstall holds operation.lock. Stop an already queued oneshot before its
        # host scripts are removed; it cannot acquire the held lock or delete data.
        run(["systemctl", "stop", name + ".service"], check=True,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30)
        for filename in payloads:
            (directory / filename).unlink(missing_ok=True)
    elif action == "install":
        for filename, payload in payloads.items():
            target = directory / filename
            if target.exists():
                continue
            descriptor, temporary = tempfile.mkstemp(dir=directory, prefix=filename + ".", suffix=".new")
            temporary = Path(temporary)
            try:
                with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
                    handle.write(payload)
                    handle.flush()
                    os.fsync(handle.fileno())
                if target.exists() or target.is_symlink():
                    raise ValueError("Maintenance unit changed during installation.")
                temporary.replace(target)
            finally:
                temporary.unlink(missing_ok=True)
    else:
        raise ValueError("Unknown maintenance action.")
    if os.name == "posix":
        descriptor = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    run(["systemctl", "daemon-reload"], check=True,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30)
    if action == "install":
        run(["systemctl", "enable", "--now", name + ".timer"], check=True,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30)


if __name__ == "__main__":
    try:
        if os.name != "posix" or os.geteuid() != 0:
            raise ValueError("Root Linux maintenance required.")
        action, root = sys.argv[1:]
        apply(Path(root).absolute(), Path("/etc/systemd/system"), action)
    except (OSError, ValueError, subprocess.SubprocessError):
        sys.exit("Private retention timer could not be safely updated; retain existing units and run the locked maintenance command manually.")

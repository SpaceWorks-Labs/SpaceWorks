#!/usr/bin/env python3
"""Bind removal to the recorded project and independently owned local volumes."""
import json
from pathlib import Path
import re
import subprocess
import sys


def docker(*args):
    return subprocess.check_output(["docker", *args], text=True, stderr=subprocess.DEVNULL, timeout=15)


def main():
    from private_files import check_private
    root, purge = Path(sys.argv[1]).absolute(), sys.argv[2] == "1"
    marker = root / ".spaceworks-managed-files.json"
    check_private(marker)
    record = json.loads(marker.read_text())
    config = json.load(sys.stdin)
    project = config.get("name")
    if (record.get("schema_version") != 1
            or not isinstance(project, str) or not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", project)
            or record.get("project") != project or record.get("root") != str(root)
            or record.get("phase") != "complete" or record.get("owner") != root.stat().st_uid
            or record.get("release") != (root / ".spaceworks-version").read_text().strip()):
        raise ValueError("Unrecorded or redirected project.")
    if not purge:
        return
    for service in config.get("services", {}).values():
        if service.get("volume_driver") not in {None, "local"}:
            raise ValueError("Non-local anonymous volume driver.")
    existing = set(docker("volume", "ls", "--format", "{{.Name}}").splitlines())
    for key, volume in config.get("volumes", {}).items():
        if volume.get("external") is True:
            continue
        if volume.get("external") not in {None, False}:
            raise ValueError("Invalid volume declaration.")
        name = volume.get("name", "")
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", name):
            raise ValueError("Invalid volume identity.")
        if name not in existing:
            continue
        facts = json.loads(docker("volume", "inspect", name))
        if not isinstance(facts, list) or len(facts) != 1:
            raise ValueError("Unproven volume.")
        item = facts[0]
        labels = item.get("Labels") or {}
        if (item.get("Name") != name or item.get("Driver") != "local" or item.get("Options")
                or labels.get("com.docker.compose.project") != project
                or labels.get("com.docker.compose.volume") != key):
            raise ValueError("Foreign or non-local volume.")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, TypeError, KeyError, IndexError, OSError, AttributeError, subprocess.SubprocessError):
        sys.exit("Uninstall refused unrecorded project or volume ownership; services and data were retained.")

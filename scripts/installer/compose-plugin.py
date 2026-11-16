#!/usr/bin/env python3
"""Stage an upstream Compose ELF only after SHA-256 and architecture checks."""
import hashlib
import importlib.util
from pathlib import Path
import re
import struct
import sys

spec = importlib.util.spec_from_file_location("release_fetch", Path(__file__).with_name("release-fetch.py"))
fetch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fetch)


def main():
    architecture, target = sys.argv[1:]
    target = Path(target)
    if architecture not in {"x86_64", "aarch64"}:
        raise ValueError("Unsupported Compose architecture.")
    release = fetch.fetch_json("https://api.github.com/repos/docker/compose/releases/latest", target / "compose.json")
    tag = release["tag_name"]
    if not re.fullmatch(r"v[0-9]+\.[0-9]+\.[0-9]+", tag) or release.get("draft") is not False or release.get("prerelease") is not False:
        raise ValueError("Invalid Compose release.")
    name = "docker-compose-linux-" + architecture
    base = "https://github.com/docker/compose/releases/download/" + tag + "/"
    fetch.download(base + name, target / "compose-plugin", 100_000_000, 180)
    fetch.download(base + name + ".sha256", target / "compose.sha256", 1024)
    checksum = (target / "compose.sha256").read_text().split()
    if not checksum or not re.fullmatch(r"[0-9a-f]{64}", checksum[0]):
        raise ValueError("Invalid Compose checksum.")
    with (target / "compose-plugin").open("rb") as handle:
        digest = hashlib.sha256()
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
        if digest.hexdigest() != checksum[0]:
            raise ValueError("Compose checksum mismatch.")
        handle.seek(0)
        header = handle.read(20)
    if (header[:6] != b"\x7fELF\x02\x01" or len(header) != 20
            or struct.unpack("<H", header[18:20])[0] != {"x86_64": 62, "aarch64": 183}[architecture]):
        raise ValueError("Compose ELF architecture mismatch.")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, KeyError, TypeError):
        sys.exit("Compose plugin verification failed; the installed executable was not changed.")

#!/usr/bin/env python3
"""Repository rules the Checks workflow enforces (owner decision #108).

1. The 300-line ceiling from CLAUDE.md: every git-tracked, non-migration, non-test,
   non-generated source file under backend/apps, backend/config and frontend/src must
   be 300 lines or fewer, unless it is on the small explicit ALLOWLIST below.
2. CLAUDE.md and AGENTS.md are one document under two names: byte-identical.

Only tracked files are measured, so the local-only test trees (backend/tests/,
frontend/src/**/*.test.ts(x)) never affect the result.

Run locally from anywhere inside the repository:  python scripts/ci/check_rules.py
Exit status is 0 when every rule holds and 1 otherwise.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import PurePosixPath

CEILING = 300
SCANNED_ROOTS = ("backend/apps", "backend/config", "frontend/src")
SOURCE_SUFFIXES = {".py", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".css"}

# Files allowed over the ceiling, each with its reason. Keep this list short: an
# entry that drops back under the ceiling fails the check so it gets removed.
ALLOWLIST = {
    # Existing 0.9.2 exceptions documented in AGENTS.md; split before editing them.
    "backend/apps/machines/access.py": "Pre-existing 367-line file; ceiling enforced on touched code",
    "backend/apps/tenant_migration/source_gate_guards.py": "Pre-existing 301-line file; ceiling enforced on touched code",
    "backend/config/settings.py": "Django settings are one file until the P2 split lane lands",
}


def repo_root() -> str:
    out = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"], check=True, capture_output=True, text=True
    )
    return out.stdout.strip()


def tracked_files(root: str) -> list[str]:
    out = subprocess.run(
        ["git", "-C", root, "ls-files", "-z", "--", *SCANNED_ROOTS],
        check=True,
        capture_output=True,
    )
    return [p for p in out.stdout.decode("utf-8").split("\0") if p]


def is_excluded(path: str) -> bool:
    parts = PurePosixPath(path).parts
    name = parts[-1]
    if "migrations" in parts:
        return True
    if path.startswith("frontend/src/generated/"):
        return True
    if any(part in ("tests", "test", "__tests__") for part in parts[:-1]):
        return True
    if name.startswith("test_") or name in ("tests.py", "conftest.py"):
        return True
    return ".test." in name or ".spec." in name


def line_count(path: str) -> int:
    with open(path, "rb") as handle:
        data = handle.read()
    return data.count(b"\n") + (1 if data and not data.endswith(b"\n") else 0)


def annotate(path: str, message: str) -> None:
    if os.environ.get("GITHUB_ACTIONS") == "true":
        print(f"::error file={path}::{message}")


def check_ceiling(root: str) -> list[str]:
    failures = []
    over, stale = [], []
    tracked = tracked_files(root)
    for path in tracked:
        if PurePosixPath(path).suffix not in SOURCE_SUFFIXES or is_excluded(path):
            continue
        full = os.path.join(root, path)
        if not os.path.isfile(full):
            continue  # deleted in the working tree but still in the index
        lines = line_count(full)
        if lines > CEILING and path not in ALLOWLIST:
            over.append((lines, path))
        elif lines <= CEILING and path in ALLOWLIST:
            stale.append((lines, path))
    for path in sorted(set(ALLOWLIST) - set(tracked)):
        stale.append((0, path))

    print(f"[ceiling] {CEILING}-line ceiling over {', '.join(SCANNED_ROOTS)}")
    for path, reason in sorted(ALLOWLIST.items()):
        print(f"  allowlisted: {path} ({reason})")
    if over:
        print(f"  FAIL: {len(over)} file(s) over the ceiling:")
        for lines, path in sorted(over, reverse=True):
            print(f"    {lines:5d}  {path}")
            annotate(path, f"{lines} lines exceeds the {CEILING}-line ceiling; split it (CLAUDE.md)")
        failures.append("ceiling")
    if stale:
        print("  FAIL: allowlist entries no longer needed; remove them from scripts/ci/check_rules.py:")
        for lines, path in stale:
            print(f"    {lines:5d}  {path}")
        failures.append("allowlist")
    if not over and not stale:
        print("  ok")
    return failures


def check_twin_docs(root: str) -> list[str]:
    print("[twins] CLAUDE.md and AGENTS.md must be byte-identical")
    try:
        with open(os.path.join(root, "CLAUDE.md"), "rb") as a, open(
            os.path.join(root, "AGENTS.md"), "rb"
        ) as b:
            same = a.read() == b.read()
    except FileNotFoundError as exc:
        print(f"  FAIL: {exc.filename} is missing")
        return ["twins"]
    if same:
        print("  ok")
        return []
    print("  FAIL: CLAUDE.md and AGENTS.md differ; copy the edited one over the other")
    annotate("AGENTS.md", "AGENTS.md must be byte-identical to CLAUDE.md")
    return ["twins"]


def main() -> int:
    root = repo_root()
    failures = check_ceiling(root) + check_twin_docs(root)
    if failures:
        print(f"Rules failed: {', '.join(failures)}")
        return 1
    print("All rules passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

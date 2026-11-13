#!/usr/bin/env python3
"""Every merge or push to main must carry a strictly higher VERSION (stdlib only).

Usage:
  check_version_bump.py --base-version 0.11.2 [--root .] [--existing-tags FILE]
  check_version_bump.py --base-file path/to/base/VERSION ...

Checks, in order: head VERSION is plain semver; head > base (equal or lower fails);
every place that carries the product version agrees with VERSION; docs/release-<VERSION>.md
exists; and, when a tag list is supplied, v<VERSION> and any v<VERSION>-main.* tag do not
exist yet. Exit 0 when clean, 1 with `::error file=...::` annotations otherwise.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

SEMVER = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")
BUMP_HINT = "Run: sh scripts/bump-version.sh <new-version> (see docs/project/release-process.md)."

# (file, regex whose first group is the version, label)
CARRIERS = (
    ("backend/config/settings_schema.py", r'"VERSION":\s*"([^"]+)"', "SPECTACULAR_SETTINGS VERSION"),
    ("frontend/openapi-schema.json", r'"version":\s*"([^"]+)"', "OpenAPI snapshot info.version"),
    ("README.md", r"badge/version-([0-9]+\.[0-9]+\.[0-9]+)-", "README version badge"),
)


def parse(text: str) -> tuple[int, int, int] | None:
    match = SEMVER.match(text.strip())
    return tuple(int(part) for part in match.groups()) if match else None


def check(root: Path, base: str, tags: set[str] | None) -> list[tuple[str, str]]:
    """Return (file, message) errors; an empty list means the bump is valid."""
    errors: list[tuple[str, str]] = []
    version_file = root / "VERSION"
    head = version_file.read_text(encoding="utf-8").strip() if version_file.exists() else ""
    head_t, base_t = parse(head), parse(base)
    if head_t is None:
        return [("VERSION", f"VERSION must be a semantic version like 1.2.3 (got '{head}').")]
    if base_t is None:
        return [("VERSION", f"The base branch VERSION '{base.strip()}' is not semver; cannot compare.")]
    if head_t <= base_t:
        relation = "equal to" if head_t == base_t else "lower than"
        errors.append((
            "VERSION",
            f"VERSION {head} is {relation} the base branch VERSION {base.strip()}. "
            f"Every merge or push to main must bump VERSION to a strictly higher semver. {BUMP_HINT}",
        ))
    for rel, pattern, label in CARRIERS:
        path = root / rel
        if not path.exists():
            errors.append((rel, f"{rel} is missing but must carry the product version ({label})."))
            continue
        match = re.search(pattern, path.read_text(encoding="utf-8"))
        found = match.group(1) if match else None
        if found != head:
            errors.append((rel, f"{label} is '{found}' but VERSION is {head}. Set it to {head}. {BUMP_HINT}"))
    notes = f"docs/release-{head}.md"
    if not (root / notes).exists():
        errors.append((notes, f"{notes} is missing. Add release notes for {head}. {BUMP_HINT}"))
    if tags is not None:
        clash = sorted(t for t in tags if t == f"v{head}" or t.startswith(f"v{head}-main."))
        if clash:
            errors.append((
                "VERSION",
                f"A release/tag for {head} already exists ({', '.join(clash[:3])}). Bump to a new version.",
            ))
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--base-version", help="VERSION of the base branch (the text itself)")
    source.add_argument("--base-file", help="file holding the base branch VERSION")
    parser.add_argument("--root", default=".", help="repository root (default: .)")
    parser.add_argument("--existing-tags", help="file with one existing git tag per line")
    args = parser.parse_args(argv)
    base = args.base_version if args.base_version is not None else Path(args.base_file).read_text(encoding="utf-8")
    tags = None
    if args.existing_tags:
        tags = {line.strip() for line in Path(args.existing_tags).read_text(encoding="utf-8").splitlines() if line.strip()}
    errors = check(Path(args.root), base.strip(), tags)
    for rel, message in errors:
        print(f"::error file={rel}::{message}")
    if not errors:
        print(f"version bump ok: {base.strip()} -> {(Path(args.root) / 'VERSION').read_text().strip()}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Print the tests affected by the changes since AFFECTED_BASE, one per line.

Used by ``scripts/dev.sh affected`` and ``.githooks/pre-push``. The base defaults to the
upstream branch (else the previous commit); uncommitted and untracked changes count too.

  affected_tests.py backend   pytest paths relative to backend/, or the single word ALL
                              when shared code changed (settings, requirements, conftest)
  affected_tests.py frontend  changed frontend sources relative to frontend/, for
                              ``vitest related``, which follows their importers itself

Backend selection is by import, module-precise:
  * a changed module, plus the modules that import it (one level of dependents);
  * a change to an app's models, migrations, apps.py, views, urls, serializers or
    permissions widens to every test that imports anything from that app, because API
    tests reach those through URLs rather than imports;
  * a test file is selected when it imports one of those modules or a name inside one.
The test trees are gitignored (decision #108), so git cannot see edited test files:
pass those explicitly (``scripts/dev.sh test <paths>``).
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

SHARED = re.compile(
    r"^backend/(config/|requirements[^/]*\.txt$|Dockerfile$|conftest\.py$|manage\.py$|pytest\.ini$|tests/conftest\.py$)"
)
APP_WIDE = re.compile(r"^(models|migrations|apps|views|urls|serializers|permissions|admin)(\.py$|/)")
IMPORT = re.compile(r"^\s*(?:from\s+(apps(?:\.\w+)*)\s+import\s+([^#\n]+)|import\s+(apps(?:\.\w+)+))", re.M)


def git(*args: str) -> str:
    return subprocess.run(["git", *args], check=True, capture_output=True, text=True).stdout


def changed_files() -> list[str]:
    # Default base: the upstream branch if there is one (what is not pushed yet), else the
    # previous commit. Never a long-lived branch like origin/dev, which can be hundreds of
    # commits behind a release branch and would select everything.
    base = os.environ.get("AFFECTED_BASE")
    if not base:
        try:
            base = git("rev-parse", "--verify", "--quiet", "@{upstream}").strip()
        except subprocess.CalledProcessError:
            base = "HEAD~1"
    files = set(git("diff", "--name-only", base, "--").split())
    files |= set(git("ls-files", "--others", "--exclude-standard").split())
    return sorted(files)


def imports(path: Path) -> set[str]:
    """Every ``apps...`` module and imported name a file references, as dotted paths."""
    found: set[str] = set()
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return found
    for module, names, plain in IMPORT.findall(text):
        if plain:
            found.add(plain)
            continue
        found.add(module)
        for name in names.replace("(", " ").replace(")", " ").replace("\\", " ").split(","):
            name = name.strip().split(" as ")[0].strip()
            if name.isidentifier():
                found.add(f"{module}.{name}")
    return found


def touches(refs: set[str], targets: set[str]) -> bool:
    return any(r == t or r.startswith(t + ".") for r in refs for t in targets)


def module_of(rel: str) -> str:
    """backend/apps/events/services/x.py -> apps.events.services.x"""
    mod = rel[len("backend/"):-len(".py")].replace("/", ".")
    return mod[: -len(".__init__")] if mod.endswith(".__init__") else mod


def backend(changed: list[str]) -> list[str]:
    if any(SHARED.match(f) for f in changed):
        return ["ALL"]
    root = Path("backend")
    targets: set[str] = set()
    for f in changed:
        if not f.startswith("backend/apps/"):
            continue
        rest = f[len("backend/apps/"):]
        app, _, inner = rest.partition("/")
        if inner and APP_WIDE.match(inner):
            targets.add(f"apps.{app}")
        elif f.endswith(".py"):
            targets.add(module_of(f))
        elif inner:  # templates, static and other app data
            targets.add(f"apps.{app}")
    if not targets:
        return []
    sources = {module_of(p.as_posix()): p for p in (root / "apps").rglob("*.py")}
    dependents = {mod for mod, p in sources.items() if touches(imports(p), targets)}
    wanted = targets | dependents
    tests = sorted(
        p.relative_to(root).as_posix()
        for p in (root / "tests").rglob("test_*.py")
        if touches(imports(p), wanted)
    )
    return tests


def frontend(changed: list[str]) -> list[str]:
    return [
        f[len("frontend/"):]
        for f in changed
        if re.match(r"^frontend/src/.*\.(ts|tsx|css)$", f) and Path(f).exists()
    ]


def main() -> int:
    scope = sys.argv[1] if len(sys.argv) > 1 else ""
    if scope not in ("backend", "frontend"):
        print("usage: affected_tests.py backend|frontend", file=sys.stderr)
        return 2
    os.chdir(git("rev-parse", "--show-toplevel").strip())
    changed = changed_files()
    sys.stdout.reconfigure(newline="\n")  # bash reads this with mapfile; no CR on Windows
    print("\n".join(backend(changed) if scope == "backend" else frontend(changed)))
    return 0


if __name__ == "__main__":
    sys.exit(main())

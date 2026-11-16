#!/usr/bin/env python3
"""In-app docs hub checks (stdlib only).

Run from anywhere:  python scripts/ci/check_docs.py [--mermaid]
Checks the hub folders under docs/: front matter, unique (group, order) and titles,
relative links and #anchors (GitHub-style slugs), wording rules, and (with --mermaid,
needs node and a mermaid install, see MERMAID_HELP) every ```mermaid block.
Exit status 0 when clean, 1 otherwise.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "docs"
FOLDERS = ["guide", "architecture", "modules", "hosting", "project", "tutorials",
           "user-guides", "how-to", "api", "reference", "changelog"]
GROUPS = {"Getting started", "Tutorials", "User guides", "How-to guides", "Areas & modules",
          "Architecture", "Hosting", "API", "Reference", "Project", "Changelog"}
BANNED = [r"\blanes?\b", r"\borchestrator\b", r"handover file", r"owner rule", r"\bcodex\b",
          r"\bdevin\b", r"\bdecision 2\d\d\b", r"[A-Za-z]:\\Users", r"/home/\w+",
          r"\bcustom roles?\b", r"\bGuest Admin\b", r"scratchpad", r"\bhandover/"]
# Lines that legitimately say custom roles do not exist are allowed.
NEGATION = re.compile(r"\b(no|not|never|without|retired|removed|instead of)\b", re.I)
MERMAID_HELP = "set MERMAID_DIR to a folder where `npm install mermaid@11 jsdom` was run"

FENCE = re.compile(r"^(```|~~~)")


def slug(heading: str) -> str:
    s = heading.strip().lower()
    s = re.sub(r"[`*]", "", s)
    s = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", s)
    s = re.sub(r"[^\w\- ]", "", s, flags=re.UNICODE)
    return s.replace(" ", "-")


def parse(path: Path):
    text = path.read_text(encoding="utf-8")
    fm: dict[str, str] = {}
    body = text
    m = re.match(r"^---\r?\n(.*?)\r?\n---\r?\n", text, re.S)
    if m:
        for line in m.group(1).splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                fm[k.strip()] = v.strip().strip("\"'")
        body = text[m.end():]
    return fm, body, text[: len(text) - len(body)].count(chr(10))


def blocks(body: str):
    """Yield (kind, lineno, text) for prose lines and fenced blocks."""
    fence = None
    buf: list[str] = []
    start = 0
    for i, line in enumerate(body.splitlines(), 1):
        mm = FENCE.match(line.strip())
        if fence is None and mm:
            fence, buf, start = (mm.group(1), line.strip()[3:].strip()), [], i
            continue
        if fence and line.strip().startswith(fence[0]):
            yield ("fence:" + fence[1], start, "\n".join(buf))
            fence = None
            continue
        if fence:
            buf.append(line)
        else:
            yield ("prose", i, line)


_anchor_cache: dict[Path, set[str]] = {}


def anchors(path: Path) -> set[str]:
    if path not in _anchor_cache:
        out: set[str] = set()
        seen: dict[str, int] = {}
        _, body, _off = parse(path)
        for kind, _, line in blocks(body):
            if kind == "prose":
                h = re.match(r"^#{1,6}\s+(.*?)\s*#*\s*$", line)
                if h:
                    s = slug(h.group(1))
                    n = seen.get(s, 0)
                    seen[s] = n + 1
                    out.add(s if n == 0 else f"{s}-{n}")
                for a in re.findall(r'<a\s+(?:name|id)="([^"]+)"', line):
                    out.add(a)
        _anchor_cache[path] = out
    return _anchor_cache[path]


def main() -> int:
    errors: list[str] = []
    files = sorted(p for f in FOLDERS for p in (DOCS / f).rglob("*.md"))
    seen_order: dict[tuple, Path] = {}
    seen_title: dict[tuple, Path] = {}
    n_links = n_anchors = 0
    merm: list[tuple[Path, int, str]] = []
    for p in files:
        rel = p.relative_to(ROOT).as_posix()
        fm, body, off = parse(p)
        for k in ("title", "group", "order", "summary"):
            if not fm.get(k):
                errors.append(f"{rel}: front matter missing {k}")
        g = fm.get("group", "")
        if g and g not in GROUPS:
            errors.append(f"{rel}: unknown group '{g}'")
        if fm.get("order") and not fm["order"].isdigit():
            errors.append(f"{rel}: order must be an integer")
        for store, key, label in ((seen_order, (g, fm.get("order")), "(group, order)"),
                                  (seen_title, (g, fm.get("title")), "title")):
            if key in store and all(key):
                errors.append(f"{rel}: duplicate {label} {key} also in {store[key].name}")
            store[key] = p
        for kind, ln, text in blocks(body):
            ln += off
            if kind == "fence:mermaid":
                merm.append((p, ln, text))
                continue
            if kind != "prose":
                continue
            noinline = re.sub(r"`[^`]*`", "", text)
            for pat in BANNED:
                if re.search(pat, noinline, re.I):
                    if ("custom role" in pat or "Guest Admin" in pat) and NEGATION.search(text):
                        continue
                    errors.append(f"{rel}:{ln}: banned wording /{pat}/")
            clean = re.sub(r"`[^`]*`", "", text)
            for target in re.findall(r"\]\(([^)\s]+)", clean) + re.findall(r"<(?:a)\s+href=\"([^\"]+)", clean):
                if re.match(r"^(https?:|mailto:|tel:)", target):
                    continue
                n_links += 1
                path_part, _, frag = target.partition("#")
                dest = p if not path_part else (p.parent / path_part).resolve()
                if any(x in target for x in ("handover/", "scratchpad", "C:\\")):
                    errors.append(f"{rel}:{ln}: forbidden link {target}")
                    continue
                if not dest.exists():
                    errors.append(f"{rel}:{ln}: broken link {target}")
                    continue
                if frag and dest.suffix == ".md":
                    n_anchors += 1
                    if frag.lower() not in anchors(dest):
                        errors.append(f"{rel}:{ln}: missing anchor {target}")
    mdir = os.environ.get("MERMAID_DIR")
    parsed = 0
    if "--mermaid" in sys.argv:
        if not mdir:
            errors.append("--mermaid: " + MERMAID_HELP)
        else:
            payload = json.dumps([{"f": p.relative_to(ROOT).as_posix(), "l": ln, "t": t} for p, ln, t in merm])
            # The parser ships with the repo; it resolves mermaid/jsdom from MERMAID_DIR's node_modules.
            runner = Path(mdir) / "parse.mjs"
            shutil.copyfile(ROOT / "scripts" / "ci" / "mermaid_parse.mjs", runner)
            r = subprocess.run(["node", str(runner)], input=payload, text=True,
                               capture_output=True, cwd=mdir)
            for line in r.stdout.splitlines():
                if line.startswith("ERR "):
                    errors.append("mermaid " + line[4:])
                elif line.startswith("OK "):
                    parsed += 1
            if r.returncode not in (0, 1):
                errors.append("mermaid runner failed: " + r.stderr[-300:])
            elif parsed + sum(1 for e in errors if e.startswith("mermaid ")) != len(merm):
                errors.append(f"mermaid: only {parsed} of {len(merm)} blocks were parsed (runner output: {r.stderr[-200:]})")
    print(f"files={len(files)} links={n_links} anchors={n_anchors} mermaid_blocks={len(merm)} mermaid_parsed={parsed}")
    for e in errors:
        print(e)
    print("FAIL" if errors else "OK")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())

"""The staff routes the web SPA calls, read from the repo (frontend sources + the OpenAPI snapshot).

Same scan as `handover/reports/mobile-parity/spa_inventory.py` (git-ignored, so the test carries its own copy),
reduced to what the native-header guard needs: URL name -> the schema paths the SPA references.
"""
import glob
import itertools
import json
import re
from pathlib import Path

from django.urls import Resolver404, resolve

ROOT = Path(__file__).resolve().parents[3]
LITERAL = re.compile(
    r"""(?:"|'|`)(/(?:admin|integrations|notifications|operations|analytics|inventory|requests|machines|presence|"""
    r"""events|billing|finance|backups)[^"'`\s]*)(?:"|'|`)""")
FILLERS = ("7", "00000000-0000-0000-0000-000000000007", "x")


def _norm(path):
    return re.sub(r"\{[^}]*\}", "{}", path).rstrip("/")


def spa_schema_paths():
    """Schema paths (with `{param}`) referenced by a string literal in frontend/src, or ``None`` without a checkout."""
    schema_file = ROOT / "frontend" / "openapi-schema.json"
    if not schema_file.exists() or not (ROOT / "frontend" / "src").is_dir():
        return None
    schema = json.loads(schema_file.read_text(encoding="utf8"))
    by_norm = {}
    for path in schema["paths"]:
        by_norm.setdefault(_norm(path[len("/api/v1"):] if path.startswith("/api/v1") else path), []).append(path)
    found = set()
    for name in glob.glob(str(ROOT / "frontend" / "src" / "**" / "*.ts*"), recursive=True):
        norm = name.replace("\\", "/")
        if "/generated/" in norm or re.search(r"\.(test|spec|dev)\.|/test/", norm):
            continue
        text = Path(name).read_text(encoding="utf8", errors="ignore")
        for hit in LITERAL.finditer(text):
            key = _norm(re.sub(r"\$\{[^}]*\}", "{}", hit.group(1).split("?")[0]))
            found.update(by_norm.get(key, ()))
    return found


def match_for(schema_path):
    """``(concrete path, ResolverMatch)`` for a schema path, trying int, uuid and str fillers per placeholder."""
    count = len(re.findall(r"\{[^}]*\}", schema_path))
    for combo in itertools.product(FILLERS, repeat=min(count, 3)):
        fills = iter(combo + (combo[-1],) * (count - len(combo)) if combo else ())
        concrete = re.sub(r"\{[^}]*\}", lambda _m: next(fills), schema_path)
        try:
            return concrete, resolve(concrete)
        except Resolver404:
            continue
    return None, None

"""Decision 544: driver-specific SQLSTATE reads belong in one shared helper."""
import ast
from pathlib import Path

import pytest

APPS = Path(__file__).resolve().parents[2] / "apps"
HELPER = APPS / "core/db.py"
ATTRIBUTES = {"sqlstate", "pgcode"}


def _driver_reads(source):
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Attribute) and isinstance(node.ctx, ast.Load) and node.attr in ATTRIBUTES:
            yield node.lineno
        elif (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
              and node.func.id in {"getattr", "hasattr"} and len(node.args) >= 2
              and isinstance(node.args[1], ast.Constant) and node.args[1].value in ATTRIBUTES):
            yield node.lineno


def test_apps_only_read_driver_sqlstate_inside_shared_helper():
    violations = [
        f"{path.relative_to(APPS)}:{line}"
        for path in sorted(APPS.rglob("*.py")) if path != HELPER
        for line in _driver_reads(path.read_text(encoding="utf-8-sig"))
    ]
    assert violations == [], "Use apps.core.db.sqlstate(exc): " + ", ".join(violations)


@pytest.mark.parametrize("source", [
    "exc.sqlstate", "exc.pgcode", 'getattr(exc, "sqlstate", None)',
    'getattr(exc.__cause__, "pgcode", None)', 'hasattr(exc, "pgcode")',
])
def test_guard_detects_direct_and_reflective_driver_reads(source):
    assert list(_driver_reads(source)) == [1]


def test_guard_allows_shared_helper_calls_and_unrelated_literals():
    assert list(_driver_reads('sqlstate(exc)\nlabel = "pgcode"')) == []

"""Root pytest hooks for the backend suite.

Tests that drive Django's migration executor (unapply/re-apply real migrations) are tagged `migration`
automatically. They rebuild Django's migration state, which is slow and memory-heavy on a large graph, so
shared local runners may deselect them with `-m "not migration"` (decision 487). CI runs everything; the tag
never skips a test on its own.
"""
from pathlib import Path

import pytest

_MIGRATION_SIGNATURES = ("MigrationExecutor", "executor.migrate(", 'call_command("migrate"', "call_command('migrate'")
_seen: dict[str, bool] = {}


def _drives_migrations(path: Path) -> bool:
    key = str(path)
    if key not in _seen:
        try:
            source = path.read_text(encoding="utf-8")
        except OSError:
            source = ""
        _seen[key] = any(signature in source for signature in _MIGRATION_SIGNATURES)
    return _seen[key]


@pytest.hookimpl(tryfirst=True)
def pytest_collection_modifyitems(config, items):
    for item in items:
        if _drives_migrations(Path(str(item.fspath))):
            item.add_marker(pytest.mark.migration)

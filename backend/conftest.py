"""Root pytest hooks for the backend suite.

Tests that drive Django's migration executor (unapply/re-apply real migrations) are tagged `migration`
automatically. They rebuild Django's migration state, which is slow and memory-heavy on a large graph, so
shared local runners may deselect them with `-m "not migration"` (decision 487). CI runs everything; the tag
never skips a test on its own.
"""
from pathlib import Path

import pytest

from tests.areas import AREAS, areas_for_test, owners_for_app

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
        path = Path(str(item.fspath))
        if _drives_migrations(path):
            item.add_marker(pytest.mark.migration)
        names = set(areas_for_test(path))
        # Registry-driven matrices often name their areas only in parametrized cases.
        params = getattr(getattr(item, "callspec", None), "params", {})
        names.update(_parameter_areas(params.values()))
        for name in sorted(names):
            item.add_marker(getattr(pytest.mark, f"area_{name}"))


def _parameter_areas(values):
    from apps.makerspaces.capability_definitions import FEATURES

    names, visited, pending = set(), set(), list(values)
    while pending:
        value = pending.pop()
        if isinstance(value, str):
            if value in AREAS:
                names.add(value)
            if value in FEATURES:
                feature = FEATURES[value]
                names.update(module for module in (feature.parent_module, *feature.requires_modules) if module)
                if feature.app_label:
                    names.update(owners_for_app(feature.app_label))
                if value.split(".")[0] in AREAS:
                    names.add(value.split(".")[0])
                if value.startswith("loans."):
                    names.update(("inventory", "lending"))
                if value.startswith(("charges.", "billing.", "finance.")):
                    names.add("payments_ledger")
            if value.startswith("apps."):
                names.update(owners_for_app(value.split(".")[1]))
        elif isinstance(value, (dict, tuple, list, set, frozenset)) and id(value) not in visited:
            visited.add(id(value))
            pending.extend((*value.keys(), *value.values()) if isinstance(value, dict) else value)
    return names


def pytest_terminal_summary(terminalreporter):
    from collections import Counter

    items = terminalreporter._session.items
    counts = Counter(name for item in items for name in {
        marker.name[5:] for marker in item.iter_markers() if marker.name.startswith("area_")
    })
    terminalreporter.write_sep("-", "selected test counts by area (overlap is intentional)")
    terminalreporter.write_line(", ".join(f"{name}={counts[name]}" for name in sorted(counts)))


def _drop_derived_objects(connection):
    """What `manage.py migrate` does around a schema change, for a bare MigrationExecutor.

    The analytics views (pre_migrate) and the generated tenant RLS policies are derived objects that
    `migrate` rebuilds afterwards (post_migrate). While they exist they block dropping or retyping the
    columns, and the helper function, they read, so a rewind through such a migration fails with
    "cannot alter type / cannot drop ... because other objects depend on it".
    """
    if connection.vendor != "postgresql":
        return
    from apps.analytics import db_ddl
    from apps.tenant_rls.policies import FIXED_POLICY, TENANT_POLICY

    with connection.cursor() as cursor:
        db_ddl.drop_view_schemas(cursor)
        cursor.execute("SELECT schemaname, tablename, policyname FROM pg_policies WHERE policyname IN (%s, %s)",
                       [TENANT_POLICY, FIXED_POLICY])
        for schema, table, policy in cursor.fetchall():
            cursor.execute(f'DROP POLICY IF EXISTS "{policy}" ON "{schema}"."{table}"')


@pytest.fixture(autouse=True)
def _migration_tests_drop_derived_objects(request, monkeypatch):
    """Tests tagged `migration` get the derived-object handling above, then the objects are rebuilt."""
    if request.node.get_closest_marker("migration") is None:
        yield
        return
    from django.db import connection
    from django.db.migrations.executor import MigrationExecutor

    original, flag = MigrationExecutor.migrate, {"dropped": False}

    def migrate(self, targets, *args, **kwargs):
        if not flag["dropped"]:
            _drop_derived_objects(self.connection)
            flag["dropped"] = True
        return original(self, targets, *args, **kwargs)

    monkeypatch.setattr(MigrationExecutor, "migrate", migrate)
    yield
    monkeypatch.undo()
    if flag["dropped"]:
        from apps.analytics.db_sync import sync as analytics_sync
        from apps.tenant_rls.sync import sync as rls_sync

        connection.ensure_connection()
        rls_sync()
        analytics_sync(force=True)

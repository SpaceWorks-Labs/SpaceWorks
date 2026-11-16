"""Root pytest hooks for the backend suite.

Tests that drive Django's migration executor (unapply/re-apply real migrations) are tagged `migration`
automatically. They rebuild Django's migration state, which is slow and memory-heavy on a large graph, so
shared local runners may deselect them with `-m "not migration"` (decision 487). CI runs everything; the tag
never skips a test on its own.
"""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from time import monotonic

import pytest

from tests.areas import AREAS, areas_for_test, owners_for_app

_MIGRATION_SIGNATURES = ("MigrationExecutor", "executor.migrate(", 'call_command("migrate"', "call_command('migrate'")
_seen: dict[str, bool] = {}


class _BoundedThreadPoolExecutor(ThreadPoolExecutor):
    """Test workers must join within one deadline, including on assertion failure.

    Future.result(timeout=...) alone still lets __exit__ wait forever. Python's
    executor has no public timed join; inspect its worker set only in this harness.
    """

    def __exit__(self, exc_type, _exc, _traceback):
        self.shutdown(wait=False, cancel_futures=exc_type is not None)
        deadline = monotonic() + 30
        for worker in self._threads:
            worker.join(timeout=max(0, deadline - monotonic()))
        alive = sorted(worker.name for worker in self._threads if worker.is_alive())
        if alive:
            pytest.fail(f"Connection hygiene failure: test workers did not join within 30s: {alive}",
                        pytrace=False)
        return False


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


def _check_transaction_connection_hygiene(nodeid):
    """Decision 543: release leaked transactions before TRUNCATE can deadlock."""
    from django.db import connection, connections

    if connection.vendor != "postgresql":
        return
    with connection.cursor() as cursor:
        cursor.execute("SELECT current_database()")
        database = cursor.fetchone()[0]
    if not database.startswith("test_"):
        raise RuntimeError(f"Refusing connection cleanup outside a test_ database: {database}")
    for extra in connections.all(initialized_only=True):
        if extra.alias != connection.alias:
            extra.close()
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT pid, pg_terminate_backend(pid) FROM pg_stat_activity "
            "WHERE datname = %s AND pid <> pg_backend_pid() "
            "AND state IN ('idle in transaction', 'idle in transaction (aborted)')",
            [database],
        )
        leaked = cursor.fetchall()
    if leaked:
        pytest.fail(f"Connection hygiene failure in {nodeid}: leaked idle-in-transaction "
                    f"backends in {database} (pid, terminated): {leaked}. "
                    "Close connections in each worker's finally block and join threads with a timeout.",
                    pytrace=False)


@pytest.fixture(autouse=True)
def _transaction_connection_hygiene(request):
    marker = request.node.get_closest_marker("django_db")
    transactional = marker and any(marker.kwargs.get(key) for key in
                                  ("transaction", "reset_sequences", "serialized_rollback"))
    if not transactional and not set(request.fixturenames).intersection({
        "transactional_db", "django_db_reset_sequences", "django_db_serialized_rollback",
    }):
        yield
        return
    # Acquiring the DB fixture first makes our finalizer run BEFORE its flush.
    request.getfixturevalue("_django_db_helper")
    try:
        yield
    finally:
        _check_transaction_connection_hygiene(request.node.nodeid)


def _drop_derived_objects(connection):
    """Test-only suspension for historical schema rewinds, including RLS helper removal.

    Runtime pre_migrate deliberately retains views. Bare-executor tests instead capture
    the complete analytics dependency closure and restore it after their schema returns.
    RESTRICT and preflight refusal protect custom objects; no schema CASCADE is used.
    """
    if connection.vendor != "postgresql":
        return []
    from django.db import transaction
    from apps.analytics.db_ddl import VIEW_SCHEMAS
    from apps.analytics.migration_views import suspend
    from apps.tenant_rls.policies import FIXED_POLICY, TENANT_POLICY

    with transaction.atomic(using=connection.alias), connection.cursor() as cursor:
        cursor.execute("SELECT c.oid FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
                       "WHERE n.nspname=ANY(%s) AND c.relkind IN ('v','m')", [list(VIEW_SCHEMAS)])
        snapshot = suspend(connection, roots=[oid for (oid,) in cursor.fetchall()])
        cursor.execute("SELECT schemaname, tablename, policyname FROM pg_policies WHERE policyname IN (%s, %s)",
                       [TENANT_POLICY, FIXED_POLICY])
        for schema, table, policy in cursor.fetchall():
            q = connection.ops.quote_name
            cursor.execute(f'DROP POLICY IF EXISTS {q(policy)} ON {q(schema)}.{q(table)}')
    return snapshot


@pytest.fixture(autouse=True)
def _migration_tests_drop_derived_objects(request, monkeypatch):
    """Tests tagged `migration` get the derived-object handling above, then the objects are rebuilt."""
    if request.node.get_closest_marker("migration") is None:
        yield
        return
    from django.db import connection, transaction
    from django.db.migrations.executor import MigrationExecutor

    original, flag = MigrationExecutor.migrate, {"dropped": False, "snapshot": []}

    def migrate(self, targets, *args, **kwargs):
        if not flag["dropped"]:
            flag["snapshot"] = _drop_derived_objects(self.connection)
            flag["dropped"] = True
        return original(self, targets, *args, **kwargs)

    monkeypatch.setattr(MigrationExecutor, "migrate", migrate)
    yield
    monkeypatch.undo()
    if flag["dropped"]:
        from apps.analytics.db_sync import sync as analytics_sync
        from apps.analytics.migration_views import restore
        from apps.tenant_rls.sync import sync as rls_sync

        connection.ensure_connection()
        rls_sync()
        with transaction.atomic(using=connection.alias):
            restore(connection, flag["snapshot"])
        analytics_sync(force=True)

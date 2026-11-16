"""Committed, two-session decision-518 races without a migration-graph rewind."""
from contextlib import contextmanager
from decimal import Decimal
from queue import Queue
from threading import Event, Thread
from time import monotonic, sleep
from uuid import uuid4

import pytest
from django.db import connection, connections, transaction
from django.test.utils import CaptureQueriesContext

from apps.analytics import migration_views
from apps.analytics.migration_acl import as_role
from tests.analytics.money_upgrade_fixtures import metadata

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.fixture
def committed_reports():
    """Only private, disposable objects are committed; both sessions can see them."""
    started = monotonic()
    q = connection.ops.quote_name
    suffix = uuid4().hex[:12]
    schema = 'cx1_refresh_' + suffix
    roles = {key: f'cx1_refresh_{key}_{suffix}' for key in ('migrator', 'owner')}
    source, base = f'{q(schema)}.source', f'{q(schema)}.base'
    materials = [f'{q(schema)}.{q(name)}' for name in ('retained_a', 'retained_b')]
    with transaction.atomic(), connection.cursor() as cursor:
        cursor.execute("SET LOCAL lock_timeout='3s'")
        cursor.execute("SET LOCAL statement_timeout='5s'")
        cursor.execute('SELECT current_user')
        original = cursor.fetchone()[0]
        for role in roles.values():
            cursor.execute(f'CREATE ROLE {q(role)} NOLOGIN NOINHERIT NOSUPERUSER NOBYPASSRLS')
            cursor.execute(f'GRANT {q(role)} TO {q(original)} WITH INHERIT FALSE, SET TRUE')
        cursor.execute(f'GRANT {q(roles["owner"])} TO {q(roles["migrator"])} WITH INHERIT FALSE, SET TRUE')
        cursor.execute(f'CREATE SCHEMA {q(schema)} AUTHORIZATION {q(roles["migrator"])}')
        cursor.execute(f'GRANT USAGE,CREATE ON SCHEMA {q(schema)} TO {q(roles["owner"])}')
        cursor.execute(f'CREATE TABLE {source} (id integer PRIMARY KEY,amount numeric(12,2))')
        cursor.execute(f'INSERT INTO {source} VALUES (1,12.35),(2,99.99)')
        cursor.execute(f'ALTER TABLE {source} OWNER TO {q(roles["migrator"])}')
        cursor.execute(f'GRANT SELECT ON {source} TO {q(roles["owner"])}')
        with as_role(cursor, q, roles['owner']):
            cursor.execute(f'CREATE VIEW {base} AS SELECT id,amount FROM {source}')
            for target in materials:
                cursor.execute(f'CREATE MATERIALIZED VIEW {target} AS SELECT * FROM {base} WITH NO DATA')
                cursor.execute(f'CREATE UNIQUE INDEX ON {target} (id)')
                cursor.execute(f'COMMENT ON MATERIALIZED VIEW {target} IS %s', ['retained snapshot'])
        cursor.execute(f'CREATE TABLE {q(schema)}.unaffected (n integer)')
        cursor.execute(f'INSERT INTO {q(schema)}.unaffected VALUES (7)')
    world = dict(schemas={'fixture': schema}, roles=roles, source=source, base=base, materials=materials)
    try:
        yield world
    finally:
        with transaction.atomic(), connection.cursor() as cursor:
            cursor.execute("SET LOCAL lock_timeout='3s'")
            cursor.execute("SET LOCAL statement_timeout='5s'")
            cursor.execute(f'DROP SCHEMA {q(schema)} CASCADE')
            for role in roles.values():
                cursor.execute(f'DROP ROLE {q(role)}')
        assert monotonic() - started < 30


@contextmanager
def _migrating(world):
    with transaction.atomic(), connection.cursor() as cursor:
        cursor.execute("SET LOCAL lock_timeout='3s'")
        cursor.execute("SET LOCAL statement_timeout='5s'")
        cursor.execute(f'SET LOCAL SESSION AUTHORIZATION {connection.ops.quote_name(world["roles"]["migrator"])}')
        cursor.execute('SELECT rolsuper,rolinherit,rolbypassrls FROM pg_roles WHERE rolname=current_user')
        assert cursor.fetchone() == (False, False, False)
        cursor.execute("SELECT pg_has_role(current_user,%s,'USAGE'),pg_has_role(current_user,%s,'SET')",
                       [world['roles']['owner']] * 2)
        assert cursor.fetchone() == (False, True)
        yield


def _identities(world):
    with connection.cursor() as cursor:
        cursor.execute('SELECT c.oid,c.relname,c.relkind FROM pg_class c '
                       'JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname=%s ORDER BY c.oid',
                       [world['schemas']['fixture']])
        return cursor.fetchall()


def _assert_locks(cursor, oids):
    cursor.execute("SELECT relation,mode,granted FROM pg_locks WHERE pid=pg_backend_pid() "
                   "AND locktype='relation' AND relation=ANY(%s::oid[]) AND mode='AccessExclusiveLock' "
                   'ORDER BY relation', [oids])
    assert cursor.fetchall() == [(oid, 'AccessExclusiveLock', True) for oid in sorted(oids)]


@contextmanager
def _refresher(world, *, change_source=False):
    start, ready, done, results = Event(), Event(), Event(), Queue()
    signals = dict(start=start, done=done)

    def run():
        db = connections['default']
        try:
            with transaction.atomic(), db.cursor() as cursor:
                cursor.execute("SET LOCAL lock_timeout='3s'")
                cursor.execute("SET LOCAL statement_timeout='5s'")
                cursor.execute(f'SET LOCAL SESSION AUTHORIZATION {db.ops.quote_name(world["roles"]["owner"])}')
                cursor.execute('SELECT pg_backend_pid()')
                signals['pid'] = cursor.fetchone()[0]
                ready.set()
                assert start.wait(5), 'migration never reached the deterministic barrier'
                for target in world['materials']:
                    cursor.execute(f'REFRESH MATERIALIZED VIEW {target}')
            if change_source:
                with db.cursor() as cursor:
                    cursor.execute("SET lock_timeout='3s'")
                    cursor.execute("SET statement_timeout='5s'")
                    cursor.execute(f'UPDATE {world["source"]} SET amount=44.44 WHERE id=1')
                    cursor.execute(f'DELETE FROM {world["source"]} WHERE id=2')
            results.put(('refreshed', None))
        except BaseException as exc:
            results.put(('error', exc))
        finally:
            db.close()
            ready.set()
            done.set()

    worker = Thread(target=run, daemon=True)
    started = monotonic()
    worker.start()
    try:
        assert ready.wait(5), 'refresh connection did not become ready'
        yield signals
    finally:
        start.set()
        worker.join(15)
        assert not worker.is_alive(), 'bounded refresh worker did not finish'
    state, error = results.get_nowait()
    if error is not None:
        raise error
    assert state == 'refreshed'
    assert monotonic() - started < 30


def _assert_refresh_waiting(cursor, signals, oid):
    deadline = monotonic() + 2
    while monotonic() < deadline:
        cursor.execute("SELECT mode,granted,pg_backend_pid()=ANY(pg_blocking_pids(pid)) FROM pg_locks "
                       "WHERE pid=%s AND locktype='relation' AND relation=%s AND NOT granted",
                       [signals['pid'], oid])
        rows = cursor.fetchall()
        if rows:
            assert rows == [('AccessExclusiveLock', False, True)]
            assert signals['done'].is_set() is False
            return
        assert signals['done'].is_set() is False, 'refresh escaped the migration locks'
        sleep(0.01)
    pytest.fail('refresh did not wait on the migration relation lock within two seconds')


def test_refresh_committed_after_discovery_refuses_whole_set_before_drop(monkeypatch, committed_reports):
    world = committed_reports
    identities, before = _identities(world), metadata(world)
    real_affected, discoveries = migration_views.affected, []
    with _refresher(world, change_source=True) as signals:
        def after_discovery(cursor, columns):
            ordered = real_affected(cursor, columns)
            discoveries.append(ordered)
            if len(discoveries) == 1:
                signals['start'].set()
                assert signals['done'].wait(5), 'winning refresh did not commit at the barrier'
            return ordered

        monkeypatch.setattr(migration_views, 'affected', after_discovery)
        with CaptureQueriesContext(connection) as queries:
            with pytest.raises(RuntimeError) as error, _migrating(world):
                migration_views.suspend(connection, [(world['source'], 'amount')])
        assert str(error.value) == (
            'Unsupported populated materialized views: ' + ', '.join(world['materials']) + '. '
            'Drop them or refresh them WITH NO DATA yourself before retrying; no objects have been dropped.'
        )
        assert len(discoveries) == 1  # The locked revalidation refuses inside the real affected().
        assert [row['sql'] for row in queries.captured_queries if row['sql'].lstrip().upper().startswith('DROP ')] == []
    assert _identities(world) == identities
    assert metadata(world) == [{**view, 'populated': True} if view['kind'] == 'm' else view for view in before]
    with connection.cursor() as cursor:
        for target in world['materials']:
            cursor.execute(f'SELECT * FROM {target} ORDER BY id')
            assert cursor.fetchall() == [(1, Decimal('12.35')), (2, Decimal('99.99'))]
        cursor.execute(f'SELECT * FROM {world["source"]} ORDER BY id')
        assert cursor.fetchall() == [(1, Decimal('44.44'))]
        cursor.execute("SELECT format_type(atttypid,atttypmod) FROM pg_attribute "
                       "WHERE attrelid=to_regclass(%s) AND attname='amount'", [world['source']])
        assert cursor.fetchone() == ('numeric(12,2)',)


def test_refresh_after_locks_waits_through_suspend_alter_restore_and_commit(monkeypatch, committed_reports):
    world = committed_reports
    identities, before = _identities(world), metadata(world)
    oids = [oid for oid, _, kind in identities if kind in ('v', 'm')]
    first_material = next(oid for oid, name, _ in identities if name == 'retained_a')
    real_capture, captures = migration_views.capture, []
    with connection.cursor() as cursor:
        cursor.execute('SELECT pg_relation_filenode(to_regclass(%s))', [world['source']])
        source_file = cursor.fetchone()[0]
    with _refresher(world) as signals:
        def before_capture(cursor, q, oid):
            _assert_locks(cursor, oids)
            if not captures:
                signals['start'].set()
                _assert_refresh_waiting(cursor, signals, first_material)
            captures.append(oid)
            return real_capture(cursor, q, oid)

        monkeypatch.setattr(migration_views, 'capture', before_capture)
        with _migrating(world), connection.cursor() as cursor:
            snapshot = migration_views.suspend(connection, [(world['source'], 'amount')])
            assert sorted(captures) == sorted(oids)
            _assert_locks(cursor, oids)
            _assert_refresh_waiting(cursor, signals, first_material)
            # Keep the scale: this ALTER does not rewrite the source heap. A raw
            # REFRESH already has its statement snapshot when it waits; PG16's
            # table rewrites are not MVCC-safe for that old snapshot. Exercise
            # the actual money rewrite separately, with refresh after commit.
            cursor.execute(f'ALTER TABLE {world["source"]} ALTER COLUMN amount TYPE numeric(13,2)')
            cursor.execute('SELECT pg_relation_filenode(to_regclass(%s))', [world['source']])
            assert cursor.fetchone() == (source_file,)
            migration_views.restore(connection, snapshot)
            assert metadata(world) == before
            _assert_locks(cursor, oids)
            _assert_refresh_waiting(cursor, signals, first_material)
        assert signals['done'].wait(5), 'serialized refresh did not finish after migration commit'
    assert metadata(world) == [{**view, 'populated': True} if view['kind'] == 'm' else view for view in before]
    with connection.cursor() as cursor:
        for target in world['materials']:
            cursor.execute(f'SELECT * FROM {target} ORDER BY id')
            assert cursor.fetchall() == [(1, Decimal('12.35')), (2, Decimal('99.99'))]
        cursor.execute(f'SELECT * FROM {connection.ops.quote_name(world["schemas"]["fixture"])}.unaffected')
        assert cursor.fetchall() == [(7,)]
        cursor.execute("SELECT format_type(atttypid,atttypmod) FROM pg_attribute "
                       "WHERE attrelid=to_regclass(%s) AND attname='amount'", [world['source']])
        assert cursor.fetchone() == ('numeric(13,2)',)


def test_money_rewrite_keeps_source_and_refreshes_restored_relations_after_commit(committed_reports):
    world = committed_reports
    before = metadata(world)
    identities = {name: oid for oid, name, kind in _identities(world) if kind in ('r', 'v', 'm')}
    with connection.cursor() as cursor:
        cursor.execute('SELECT pg_relation_filenode(to_regclass(%s))', [world['source']])
        source_file = cursor.fetchone()[0]
    with _refresher(world) as signals:
        with _migrating(world), connection.cursor() as cursor:
            snapshot = migration_views.suspend(connection, [(world['source'], 'amount')])
            cursor.execute(f'ALTER TABLE {world["source"]} ALTER COLUMN amount TYPE numeric(13,3)')
            cursor.execute(f'UPDATE {world["source"]} SET amount=44.444 WHERE id=1')
            cursor.execute('SELECT pg_relation_filenode(to_regclass(%s))', [world['source']])
            assert cursor.fetchone()[0] != source_file
            migration_views.restore(connection, snapshot)
            assert metadata(world) == before  # Both materialized views remain WITH NO DATA.
            assert signals['start'].is_set() is False
            assert signals['done'].is_set() is False
        # The upgrade stops writers. Start the refresh statement only after the
        # rewriting transaction commits, so its snapshot includes the new heap.
        assert connection.in_atomic_block is False
        restored = {name: oid for oid, name, kind in _identities(world) if kind in ('r', 'v', 'm')}
        assert set(restored) == set(identities)
        assert restored['source'] == identities['source']
        for name in ('base', 'retained_a', 'retained_b'):
            assert restored[name] != identities[name]
        with connection.cursor() as cursor:
            cursor.execute(f'SELECT * FROM {world["source"]} ORDER BY id')
            assert cursor.fetchall() == [(1, Decimal('44.444')), (2, Decimal('99.990'))]
        signals['start'].set()
        assert signals['done'].wait(5), 'post-commit refresh did not finish'
    assert metadata(world) == [{**view, 'populated': True} if view['kind'] == 'm' else view for view in before]
    with connection.cursor() as cursor:
        for target in (world['source'], *world['materials']):
            cursor.execute(f'SELECT * FROM {target} ORDER BY id')
            assert cursor.fetchall() == [(1, Decimal('44.444')), (2, Decimal('99.990'))]
        cursor.execute("SELECT format_type(atttypid,atttypmod) FROM pg_attribute "
                       "WHERE attrelid=to_regclass(%s) AND attname='amount'", [world['source']])
        assert cursor.fetchone() == ('numeric(13,3)',)


def test_suspend_refuses_autocommit_before_any_sql():
    assert connection.in_atomic_block is False
    with CaptureQueriesContext(connection) as queries, pytest.raises(RuntimeError) as error:
        migration_views.suspend(connection, [])
    assert str(error.value) == 'View suspension requires a transaction holding relation locks through restore.'
    assert queries.captured_queries == []


def test_restore_refuses_populated_capture_before_any_create(committed_reports):
    world = committed_reports
    with connection.cursor() as cursor:
        for target in world['materials']:
            cursor.execute(f'REFRESH MATERIALIZED VIEW {target}')
    identities, before = _identities(world), metadata(world)
    with CaptureQueriesContext(connection) as queries:
        with pytest.raises(RuntimeError) as error, _migrating(world):
            migration_views.restore(connection, before)
    assert str(error.value) == (
        'Unsupported populated materialized views: ' + ', '.join(world['materials']) + '. '
        'Drop them or refresh them WITH NO DATA yourself before retrying; no objects have been dropped.'
    )
    assert [row['sql'] for row in queries.captured_queries
            if row['sql'].lstrip().upper().startswith(('CREATE ', 'DROP '))] == []
    assert _identities(world) == identities
    assert metadata(world) == before


def test_changed_affected_set_refuses_before_first_drop(monkeypatch, committed_reports):
    world = committed_reports
    identities, before = _identities(world), metadata(world)
    real_affected, discoveries = migration_views.affected, []

    def add_dependent_after_discovery(cursor, columns):
        ordered = real_affected(cursor, columns)
        discoveries.append(ordered)
        if len(discoveries) == 1:
            with as_role(cursor, connection.ops.quote_name, world['roles']['owner']):
                cursor.execute(f'CREATE VIEW {connection.ops.quote_name(world["schemas"]["fixture"])}.late '
                               f'AS SELECT * FROM {world["source"]}')
        return ordered

    monkeypatch.setattr(migration_views, 'affected', add_dependent_after_discovery)
    with CaptureQueriesContext(connection) as queries:
        with pytest.raises(RuntimeError) as error, _migrating(world):
            migration_views.suspend(connection, [(world['source'], 'amount')])
    assert str(error.value) == (
        'Affected view dependencies changed while acquiring locks; retry before dropping any objects.'
    )
    assert len(discoveries) == 2
    assert [row['sql'] for row in queries.captured_queries if row['sql'].lstrip().upper().startswith('DROP ')] == []
    assert _identities(world) == identities
    assert metadata(world) == before

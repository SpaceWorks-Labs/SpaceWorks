"""An unrestorable dependent must stop the upgrade before the first DROP."""
import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from apps.analytics.migration_support import altered_columns
from apps.analytics.migration_views import suspend
from tests.analytics.money_upgrade_fixtures import historical_money, install_views, metadata
from tests.analytics.test_shop_money_migration_views import migrating

pytestmark = pytest.mark.django_db(transaction=True)


def test_dependent_function_refuses_before_any_destructive_ddl():
    with historical_money('shop') as world:
        install_views(world)
        q = connection.ops.quote_name
        function = f'{q(world["schemas"]["external"])}.blocked'
        with connection.cursor() as cursor:
            cursor.execute(f'CREATE FUNCTION {function}() RETURNS SETOF {world["base"]} '
                           f"LANGUAGE sql AS 'SELECT * FROM {world['base']}'")
        before = metadata(world)
        with CaptureQueriesContext(connection) as queries:
            with pytest.raises(RuntimeError) as error, migrating(world):
                suspend(connection, altered_columns('shop', world['state']))
        assert str(error.value) == (
            f'Cannot preserve dependent object: function {world["schemas"]["external"]}.blocked() (pg_proc)'
        )
        assert [row['sql'] for row in queries.captured_queries if row['sql'].lstrip().upper().startswith('DROP ')] == []
        assert metadata(world) == before


def test_unaffected_view_and_schema_identity_survive_suspend_restore():
    from apps.analytics.migration_views import restore

    with historical_money('shop') as world:
        install_views(world)
        before = metadata(world)
        with connection.cursor() as cursor:
            cursor.execute('SELECT oid FROM pg_class WHERE oid=to_regclass(%s)', [world['unaffected']])
            original_oid = cursor.fetchone()[0]
            cursor.execute("SELECT 'spaceworks_analytics.unaffected_table'::regclass::oid")
            table_oid = cursor.fetchone()[0]
        with migrating(world):
            snapshot = suspend(connection, altered_columns('shop', world['state']))
            assert {row['name'] for row in snapshot} == {
                'z_base', 'a_report', 'column_only', 'saved_report', 'material', 'all_rows',
            }
            with connection.cursor() as cursor:
                cursor.execute(f'SELECT * FROM {world["unaffected"]}')
                assert cursor.fetchall() == [(7,)]
            restore(connection, snapshot)
        assert metadata(world) == before
        with connection.cursor() as cursor:
            cursor.execute('SELECT oid FROM pg_class WHERE oid=to_regclass(%s)', [world['unaffected']])
            assert cursor.fetchone() == (original_oid,)
            cursor.execute("SELECT 'spaceworks_analytics.unaffected_table'::regclass::oid")
            assert cursor.fetchone() == (table_oid,)


def test_unpopulated_materialized_view_is_restored_with_no_data():
    from django.db import DatabaseError, transaction
    from apps.analytics.migration_acl import as_role

    with historical_money('shop') as world:
        install_views(world)
        before = metadata(world)
        with CaptureQueriesContext(connection) as queries:
            with migrating(world), connection.schema_editor() as editor:
                world['step'].apply(world['state'].clone(), editor)
        assert metadata(world) == before
        base = next(row for row in before if row['target'] == world['base'])
        assert [(enabled, comment, name) for _, enabled, comment, name in base['rules']] == [
            ('O', 'rule comment', 'ignore_insert'),
        ]
        assert [(enabled, comment, name) for _, enabled, comment, name in base['triggers']] == [
            ('O', 'trigger comment', 'ignore_update'),
        ]
        assert [row['sql'] for row in queries.captured_queries
                if row['sql'].startswith('ALTER TABLE ') and any(
                    mode in row['sql'] for mode in (' ENABLE ', ' DISABLE '))] == []
        creates = [row['sql'] for row in queries.captured_queries
                   if row['sql'].startswith('CREATE MATERIALIZED VIEW ')]
        assert len(creates) == 1
        assert creates[0].endswith(' WITH NO DATA')
        with pytest.raises(DatabaseError) as error, transaction.atomic():
            with connection.cursor() as cursor, as_role(cursor, connection.ops.quote_name, world['roles']['other_owner']):
                cursor.execute(f'SELECT * FROM {world["material"]}')
        assert error.value.__cause__.pgcode == '55000'


@pytest.mark.parametrize('object_kind', ['RULE', 'TRIGGER'])
@pytest.mark.parametrize('enabled', ['D', 'R', 'A'])
def test_nonstandard_view_object_state_refuses_before_drop(monkeypatch, object_kind, enabled):
    from apps.analytics import migration_views

    with historical_money('shop') as world:
        install_views(world)
        before = metadata(world)
        real_capture = migration_views.capture
        key = {'RULE': 'rules', 'TRIGGER': 'triggers'}[object_kind]
        name = {'RULE': 'ignore_insert', 'TRIGGER': 'ignore_update'}[object_kind]

        def nonstandard_capture(*args):
            row = real_capture(*args)
            if row['target'] == world['base']:
                statement, _, comment, object_name = row[key][0]
                row[key] = [(statement, enabled, comment, object_name)]
            return row

        # PG16 cannot produce these states via view DDL. Inject the captured
        # metadata to prove a nonstandard installed state is refused, never reset.
        monkeypatch.setattr(migration_views, 'capture', nonstandard_capture)
        with CaptureQueriesContext(connection) as queries:
            with pytest.raises(RuntimeError) as error, migrating(world):
                suspend(connection, altered_columns('shop', world['state']))
        assert str(error.value) == (
            f'Cannot preserve nonstandard {object_kind} state: {world["base"]}.{name} ({enabled})'
        )
        assert [row['sql'] for row in queries.captured_queries if row['sql'].lstrip().upper().startswith('DROP ')] == []
        assert metadata(world) == before


@pytest.mark.parametrize('volatile', [False, True])
def test_populated_materialized_snapshots_refuse_before_drop_with_unchanged_data(volatile):
    from decimal import Decimal

    with historical_money('shop') as world:
        install_views(world)
        q = connection.ops.quote_name
        table = f'{q(world["schemas"]["tables"])}.shop_shopvariant'
        second = f'{q(world["schemas"]["external"])}."second_snapshot"'
        sequence = f'{q(world["schemas"]["external"])}."volatile_counter"'
        with connection.cursor() as cursor:
            cursor.execute(f'REFRESH MATERIALIZED VIEW {world["material"]}')
            if volatile:
                cursor.execute(f'CREATE SEQUENCE {sequence}')
                cursor.execute(f'CREATE MATERIALIZED VIEW {second} AS '
                               f"SELECT id,price,nextval('{sequence}') AS tick FROM {table}")
            else:
                cursor.execute(f'CREATE MATERIALIZED VIEW {second} AS SELECT * FROM {world["material"]}')
            cursor.execute(f'UPDATE {table} SET price=44.44 WHERE id=1')
            cursor.execute(f'DELETE FROM {table} WHERE id=2')
            cursor.execute(f'SELECT * FROM {second} ORDER BY id')
            saved_second = cursor.fetchall()
            cursor.execute('SELECT c.oid,n.nspname,c.relname FROM pg_class c JOIN pg_namespace n '
                           'ON n.oid=c.relnamespace WHERE n.nspname=ANY(%s) ORDER BY c.oid',
                           [list(world['schemas'].values())])
            identities = cursor.fetchall()
        before = metadata(world)
        with CaptureQueriesContext(connection) as queries:
            with pytest.raises(RuntimeError) as error, migrating(world), connection.schema_editor() as editor:
                world['step'].apply(world['state'].clone(), editor)
        assert str(error.value) == (
            f'Unsupported populated materialized views: {world["material"]}, {second}. '
            'Drop them or refresh them WITH NO DATA yourself before retrying; no objects have been dropped.'
        )
        assert [row['sql'] for row in queries.captured_queries if row['sql'].lstrip().upper().startswith('DROP ')] == []
        assert metadata(world) == before
        with connection.cursor() as cursor:
            cursor.execute('SELECT c.oid,n.nspname,c.relname FROM pg_class c JOIN pg_namespace n '
                           'ON n.oid=c.relnamespace WHERE n.nspname=ANY(%s) ORDER BY c.oid',
                           [list(world['schemas'].values())])
            assert cursor.fetchall() == identities
            cursor.execute(f'SELECT id,price FROM {table} ORDER BY id')
            assert cursor.fetchall() == [(1, Decimal('44.44'))]
            cursor.execute(f'SELECT id,amount FROM {world["material"]} ORDER BY id')
            assert cursor.fetchall() == [(1, Decimal('12.35')), (2, Decimal('99.99'))]
            cursor.execute(f'SELECT * FROM {second} ORDER BY id')
            assert cursor.fetchall() == saved_second
            cursor.execute("SELECT format_type(atttypid,atttypmod) FROM pg_attribute "
                           "WHERE attrelid=to_regclass(%s) AND attname='price'", [table])
            assert cursor.fetchone() == ('numeric(12,2)',)
            if volatile:
                cursor.execute(f'SELECT last_value FROM {sequence}')
                assert cursor.fetchone() == (2,)

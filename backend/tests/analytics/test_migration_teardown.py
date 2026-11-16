"""Bounded coverage of the bare-executor teardown, without rewinding the shared graph."""
from importlib import import_module

import pytest
from django.db import connection, DatabaseError, transaction
from django.db.migrations.state import ProjectState

from apps.analytics.migration_views import restore
from tests.analytics.money_upgrade_fixtures import historical_money, install_views, metadata
from tests.analytics.test_shop_money_migration_views import _money, _schema_metadata, assert_readers

pytestmark = pytest.mark.django_db(transaction=True)


def test_actual_teardown_allows_fixed_scope_reverse_sql_and_restores_views():
    import conftest as hooks

    initial = import_module('apps.tenant_rls.migrations.0001_initial')
    sql_operation = initial.Migration.operations[-1]
    state = ProjectState()
    with historical_money('shop') as world:
        install_views(world)
        q = connection.ops.quote_name
        function = f'{q(world["schemas"]["tables"])}.spaceworks_rls_fixed_scope(text)'
        target = 'spaceworks_analytics.fixed_scope_dependency'
        dependent = f'{q(world["schemas"]["external"])}."material_dependency"'
        with connection.schema_editor() as editor:
            # Clone ONLY the initial functions into this transaction's isolated
            # first schema. The exact reverse SQL resolves there, never in public.
            sql_operation.database_forwards('tenant_rls', editor, state, state)
        with connection.cursor() as cursor:
            cursor.execute(f'CREATE VIEW {target} AS SELECT '
                           f'{q(world["schemas"]["tables"])}.spaceworks_rls_fixed_scope(current_user::text) AS scope')
            cursor.execute('COMMENT ON VIEW spaceworks_analytics.fixed_scope_dependency IS %s', ['fixed-scope caller'])
            # Unlike world['material'], this external materialized view actually
            # depends on an analytics view, rather than directly on a source table.
            cursor.execute(f'CREATE MATERIALIZED VIEW {dependent} AS SELECT * FROM {world["external"]} WITH NO DATA')
            cursor.execute(f'COMMENT ON MATERIALIZED VIEW {dependent} IS %s', ['external analytics dependent'])
            cursor.execute('SELECT to_regclass(%s)::oid', [world['material']])
            independent_oid = cursor.fetchone()[0]
            cursor.execute("SELECT 'public.spaceworks_rls_fixed_scope(text)'::regprocedure::oid")
            public_function = cursor.fetchone()[0]
            cursor.execute("SELECT 'spaceworks_analytics.unaffected_table'::regclass::oid")
            table_oid = cursor.fetchone()[0]
        before, schemas = metadata(world), _schema_metadata(world)
        independent = [row for row in before if row['target'] == world['material']]
        assert [(row['target'], row['kind'], row['populated']) for row in independent] == [
            (world['material'], 'm', False),
        ]
        with pytest.raises(DatabaseError) as error, connection.schema_editor() as editor:
            sql_operation.database_backwards('tenant_rls', editor, state, state)
        assert error.value.__cause__.pgcode == '2BP01'
        assert metadata(world) == before
        snapshot = hooks._drop_derived_objects(connection)
        assert {row['target'] for row in snapshot} == {row['target'] for row in before} - {world['material']}
        assert [(row['target'], row['kind'], row['populated']) for row in snapshot
                if row['target'] == dependent] == [(dependent, 'm', False)]
        assert metadata(world) == independent
        with connection.cursor() as cursor:
            cursor.execute('SELECT to_regclass(%s)::oid', [world['material']])
            assert cursor.fetchone() == (independent_oid,)
        assert _schema_metadata(world) == schemas
        with connection.schema_editor() as editor:
            sql_operation.database_backwards('tenant_rls', editor, state, state)
        with connection.cursor() as cursor:
            cursor.execute('SELECT to_regprocedure(%s)', [function])
            assert cursor.fetchone() == (None,)
            cursor.execute("SELECT 'public.spaceworks_rls_fixed_scope(text)'::regprocedure::oid")
            assert cursor.fetchone() == (public_function,)
        with connection.schema_editor() as editor:
            sql_operation.database_forwards('tenant_rls', editor, state, state)
        restore(connection, snapshot)
        assert metadata(world) == before
        assert _schema_metadata(world) == schemas
        _money(world, world['state'], set())
        assert_readers(world)
        with pytest.raises(DatabaseError) as unpopulated, transaction.atomic(), connection.cursor() as cursor:
            cursor.execute(f'SELECT * FROM {dependent}')
        assert unpopulated.value.__cause__.pgcode == '55000'
        with connection.cursor() as cursor:
            cursor.execute('SELECT to_regclass(%s)::oid', [world['material']])
            assert cursor.fetchone() == (independent_oid,)
            cursor.execute(f'SELECT * FROM {target}')
            assert cursor.fetchone() == ([],)
            cursor.execute("SELECT 'spaceworks_analytics.unaffected_table'::regclass::oid")
            assert cursor.fetchone() == (table_oid,)

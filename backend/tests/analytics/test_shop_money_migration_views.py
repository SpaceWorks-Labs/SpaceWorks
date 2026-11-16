"""Bounded forward upgrades from two-decimal schemas, including installed view security."""
from contextlib import contextmanager
from decimal import Decimal
from importlib import import_module

import pytest
from django.db import connection, migrations, transaction, DatabaseError

from apps.analytics.migration_support import MONEY_MIGRATIONS
from tests.analytics.money_upgrade_fixtures import (
    historical_money, install_views, install_cash_sessions, metadata, public_support_data,
)

pytestmark = pytest.mark.django_db(transaction=True)


@contextmanager
def migrating(world):
    # SET ROLE alone in a superuser session would not test SET membership checks.
    with connection.cursor() as cursor:
        cursor.execute(f'SET LOCAL SESSION AUTHORIZATION {connection.ops.quote_name(world["roles"]["migrator"])}')
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT current_user,session_user,rolsuper,rolinherit FROM pg_roles WHERE rolname=current_user')
            role = world['roles']['migrator']
            assert cursor.fetchone() == (role, role, False, False)
            for owner in ('owner', 'other_owner'):
                cursor.execute("SELECT pg_has_role(current_user,%s,'USAGE'),pg_has_role(current_user,%s,'SET')",
                               [world['roles'][owner], world['roles'][owner]])
                assert cursor.fetchone() == (False, True)
        yield
    finally:
        if connection.connection.info.transaction_status != 3:
            with connection.cursor() as cursor:
                cursor.execute(f'SET LOCAL SESSION AUTHORIZATION {connection.ops.quote_name(world["original_user"])}')


def _schema_metadata(world):
    with connection.cursor() as cursor:
        cursor.execute("SELECT oid,nspname,nspowner,nspacl::text,obj_description(oid,'pg_namespace') "
                       'FROM pg_namespace WHERE nspname=ANY(%s) ORDER BY nspname',
                       [list(world['schemas'].values())])
        return cursor.fetchall()


def _defaults(world):
    with connection.cursor() as cursor:
        cursor.execute('SELECT defaclrole,defaclnamespace,defaclobjtype,defaclacl::text FROM pg_default_acl '
                       'WHERE defaclrole IN (SELECT oid FROM pg_roles WHERE rolname=ANY(%s)) ORDER BY 1,2,3',
                       [list(world['roles'].values())])
        return cursor.fetchall()


def _money(world, state, migrated):
    q = connection.ops.quote_name
    with connection.cursor() as cursor:
        for operation in world['changed']:
            model = state.models[(world['app'], operation.model_name)]
            table = model.options['db_table']
            column = operation.field.db_column or operation.name
            cursor.execute('SELECT format_type(atttypid,atttypmod) FROM pg_attribute '
                           'WHERE attrelid=to_regclass(%s) AND attname=%s', [table, column])
            field = operation.field if (operation.model_name, operation.name) in migrated else model.fields[operation.name]
            assert cursor.fetchone() == (f'numeric({field.max_digits},{field.decimal_places})',)
            cursor.execute(f'SELECT id,{q(column)} FROM {q(table)} ORDER BY id')
            assert cursor.fetchall() == [(1, Decimal('12.35')), (2, Decimal('99.99'))]


def _select(world, role, sql, expected):
    from apps.analytics.migration_acl import as_role
    with connection.cursor() as cursor, as_role(cursor, connection.ops.quote_name, world['roles'][role]):
        cursor.execute(sql)
        assert cursor.fetchall() == expected


def _refused(world, role, sql):
    from apps.analytics.migration_acl import as_role
    with pytest.raises(DatabaseError) as error, transaction.atomic():
        with connection.cursor() as cursor, as_role(cursor, connection.ops.quote_name, world['roles'][role]):
            cursor.execute(sql)
    assert error.value.__cause__.pgcode == '42501'


def assert_readers(world):
    own = [(world['own'].pk, 1, Decimal('12.35'))]
    _select(world, 'tenant', f'SELECT * FROM {world["external"]} ORDER BY id', own)
    _select(world, 'column_reader', f'SELECT amount FROM {world["base"]} ORDER BY amount', [(Decimal('12.35'),)])
    _select(world, 'column_reader', f'SELECT amount FROM {world["column_only"]} ORDER BY amount', [(Decimal('12.35'),)])
    _select(world, 'leaf', f'SELECT * FROM {world["base"]} ORDER BY id', own)
    _select(world, 'leaf', f'SELECT amount FROM {world["column_only"]} ORDER BY amount', [(Decimal('12.35'),)])
    _refused(world, 'leaf', f'SELECT id FROM {world["column_only"]}')
    _refused(world, 'column_reader', f'SELECT id FROM {world["base"]}')
    _refused(world, 'excluded', f'SELECT * FROM {world["base"]}')
    _refused(world, 'excluded', f'SELECT * FROM {world["external"]}')
    _refused(world, 'excluded', f'SELECT * FROM {world["material"]}')
    _refused(world, 'tenant', f'SELECT * FROM {world["platform"]}')
    operation = world['changed'][0]
    column = connection.ops.quote_name(operation.field.db_column or operation.name)
    _select(world, 'platform', f'SELECT id,{column} FROM {world["platform"]} ORDER BY id',
            [(1, Decimal('12.35')), (2, Decimal('99.99'))])
    with pytest.raises(DatabaseError) as error, transaction.atomic():
        _select(world, 'other_owner', f'SELECT * FROM {world["material"]}', [])
    assert error.value.__cause__.pgcode == '55000'
    if 'cash_views' in world:
        assert_cash_readers(world)
    for switch in ('analytics', 'shop'):
        world['own'].enabled_modules = ['shop'] if switch == 'analytics' else ['analytics']
        with public_support_data():
            world['own'].save(update_fields=['enabled_modules'])
        _select(world, 'tenant', f'SELECT * FROM {world["external"]} ORDER BY id', [])
        if 'cash_views' in world:
            _select(world, 'tenant', f'SELECT * FROM {world["cash_views"]}', [])
        world['own'].enabled_modules = ['analytics', 'shop']
        with public_support_data():
            world['own'].save(update_fields=['enabled_modules'])
        _select(world, 'tenant', f'SELECT * FROM {world["external"]} ORDER BY id', own)
        if 'cash_views' in world:
            assert_cash_readers(world)


def assert_cash_readers(world):
    _select(world, 'tenant', f'SELECT cash_shift_id,variance FROM {world["cash_views"]} ORDER BY cash_shift_id',
            [(1, Decimal('12.35'))])
    _select(world, 'platform', f'SELECT cash_shift_id,variance FROM {world["cash_platform"]} ORDER BY cash_shift_id',
            [(1, Decimal('12.35')), (2, Decimal('99.99'))])
    _refused(world, 'tenant', f'SELECT * FROM {world["cash_platform"]}')
    _refused(world, 'excluded', f'SELECT * FROM {world["cash_views"]}')


def assert_variance_type(world, expected):
    table = connection.ops.quote_name(world['schemas']['tables']) + '.shop_shopcashsession'
    targets = [table, *(world[key] for key in ('cash_views', 'cash_platform') if key in world)]
    with connection.cursor() as cursor:
        for target in targets:
            cursor.execute("SELECT format_type(atttypid,atttypmod) FROM pg_attribute "
                           "WHERE attrelid=to_regclass(%s) AND attname='variance'", [target])
            assert cursor.fetchone() == (expected,)


@pytest.mark.parametrize('app', list(MONEY_MIGRATIONS))
@pytest.mark.parametrize('views_present', [True, False])
def test_historical_money_operations_upgrade_forward_without_shared_graph_rewind(app, views_present):
    with historical_money(app, schemas_present=views_present) as world:
        if views_present:
            install_views(world)
            if app == 'shop':
                install_cash_sessions(world)
            assert_readers(world)
        installed, schemas, defaults = metadata(world), _schema_metadata(world), _defaults(world)
        assert len(installed) == ((9 if app == 'shop' else 7) if views_present else 0)
        assert {row[1] for row in schemas} & {'spaceworks_analytics', 'spaceworks_analytics_platform'} == (
            {'spaceworks_analytics', 'spaceworks_analytics_platform'} if views_present else set()
        )
        with connection.cursor() as cursor:
            cursor.execute('SELECT to_regclass(%s)::oid', [world.get('unaffected', 'cx1_missing')])
            unaffected_oid = cursor.fetchone()[0]
        state = world['state'].clone()
        migrated = set()
        _money(world, state, migrated)
        with migrating(world), connection.schema_editor() as editor:
            for operation in world['step'].operations:
                before = state.clone()
                operation.state_forwards(app, state)
                operation.database_forwards(app, editor, before, state)
                if isinstance(operation, migrations.AlterField):
                    migrated.add((operation.model_name, operation.name))
                # Exact values/types after EVERY real operation, not just the last.
                _money(world, world['state'], migrated)
        assert metadata(world) == installed
        assert _schema_metadata(world) == schemas
        assert _defaults(world) == defaults
        assert getattr(connection, '_analytics_migration_views', {}) == {}
        with connection.cursor() as cursor:
            cursor.execute('SELECT to_regclass(%s)::oid', [world.get('unaffected', 'cx1_missing')])
            assert cursor.fetchone() == (unaffected_oid,)
        if views_present:
            assert_readers(world)
        if app == 'shop':
            assert_variance_type(world, 'numeric(13,3)')


@pytest.mark.parametrize('views_present', [True, False])
def test_shop_reverses_variance_alter_and_reapplies_with_analytics_views(views_present):
    # Reverse only this fixture's new tables; never rewind the shared graph.
    with historical_money('shop', schemas_present=views_present) as world:
        if views_present:
            install_views(world)
            install_cash_sessions(world)
            assert_readers(world)
        installed, schemas, defaults = metadata(world), _schema_metadata(world), _defaults(world)
        assert_variance_type(world, 'numeric(12,2)')
        with migrating(world), connection.schema_editor() as editor:
            world['step'].apply(world['state'].clone(), editor)
        _money(world, world['state'], {(op.model_name, op.name) for op in world['changed']})
        assert_variance_type(world, 'numeric(13,3)')
        assert metadata(world) == installed
        assert _schema_metadata(world) == schemas
        assert _defaults(world) == defaults
        if views_present:
            assert_readers(world)
        with migrating(world), connection.schema_editor() as editor:
            world['step'].unapply(world['state'].clone(), editor)
        _money(world, world['state'], set())
        assert_variance_type(world, 'numeric(12,2)')
        assert metadata(world) == installed
        assert _schema_metadata(world) == schemas
        assert _defaults(world) == defaults
        if views_present:
            assert_readers(world)
        with migrating(world), connection.schema_editor() as editor:
            world['step'].apply(world['state'].clone(), editor)
        _money(world, world['state'], {(op.model_name, op.name) for op in world['changed']})
        assert_variance_type(world, 'numeric(13,3)')
        assert metadata(world) == installed
        if views_present:
            assert_readers(world)


@pytest.mark.parametrize('module', [
    'bookings.0030', 'events.0092', 'inventory.0022', 'machines.0037', 'maintenance.0012',
    'makerspaces.0143', 'payments.0049', 'procurement.0011', 'shop.0004',
])
def test_each_money_alter_suspends_and_restores_views_in_both_directions(module):
    app, number = module.split('.')
    migration = import_module(f'apps.{app}.migrations.{number}_money_three_decimals')
    first, last = migration.Migration.operations[0], migration.Migration.operations[-1]
    assert first.restore is False
    assert last.restore is True

"""Real migrate callbacks and sync must not bypass dependency/ACL preservation."""
import pytest
from django.db import connection, DatabaseError, transaction
from django.test.utils import CaptureQueriesContext

from apps.analytics import db_ddl, db_sync
from apps.analytics.migration_views import capture
from tests.analytics.money_upgrade_fixtures import (
    historical_money, install_views, install_cash_sessions, enable_migrator_sync, metadata, public_support_data,
)
from tests.analytics.test_shop_money_migration_views import (
    migrating, assert_readers, assert_cash_readers, assert_variance_type, _money, _defaults, _schema_metadata, _refused, _select,
)

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.mark.parametrize('views_present', [True, False])
def test_real_callbacks_keep_views_when_host_cannot_create_roles(monkeypatch, views_present):
    with historical_money('shop', schemas_present=views_present) as world:
        if views_present:
            install_views(world)
        before, schemas, defaults = metadata(world), _schema_metadata(world), _defaults(world)
        results = []
        real_sync = db_sync.sync

        def observe(using):
            result = real_sync(using)
            results.append((result.state, result.reason))
            return result

        monkeypatch.setattr(db_sync, 'sync', observe)
        with migrating(world):
            db_sync.pre_migrate_drop(None, using=connection.alias, plan=[(world['step'], False)])
            assert metadata(world) == before
            with connection.schema_editor() as editor:
                world['step'].apply(world['state'].clone(), editor)
            db_sync.post_migrate_sync(None, using=connection.alias)
        assert results == [('skipped', 'cannot_create_roles')]
        assert metadata(world) == before
        assert _schema_metadata(world) == schemas
        assert _defaults(world) == defaults
        if views_present:
            assert_readers(world)


def test_forced_sync_retains_custom_views_and_external_dependents():
    with historical_money('shop') as world:
        install_views(world)
        before = {row['target']: row for row in metadata(world)}
        with connection.cursor() as cursor:
            cursor.execute('SELECT to_regclass(name)::oid FROM unnest(%s::text[]) name', [list(before)])
            original_oids = [oid for (oid,) in cursor.fetchall()]
        defaults = _defaults(world)
        for _ in range(2):
            with CaptureQueriesContext(connection) as queries:
                result = db_sync.sync(connection.alias, force=True)
            assert (result.state, result.reason, result.failed) == ('synced', '', {})
            assert [row['sql'] for row in queries.captured_queries if row['sql'].lstrip().upper().startswith('DROP ')] == []
            with connection.cursor() as cursor:
                cursor.execute('SELECT to_regclass(name)::oid FROM unnest(%s::text[]) name', [list(before)])
                assert [oid for (oid,) in cursor.fetchall()] == original_oids
                after = {row['target']: row for row in (capture(cursor, connection.ops.quote_name, oid)
                                                       for oid in original_oids)}
            assert after == before
            assert _defaults(world) == defaults
        result = db_sync.sync(connection.alias)
        assert (result.state, result.reason, result.failed) == ('unchanged', '', {})
        assert_readers(world)


def _cash_dependency(world):
    from apps.analytics.migration_acl import as_role

    q = connection.ops.quote_name
    target = f'{q(world["schemas"]["external"])}."cash_report"'
    with connection.cursor() as cursor:
        owner = world['roles']['other_owner']
        cursor.execute(f'GRANT USAGE ON SCHEMA {q(world["schemas"]["views"])} TO {q(owner)}')
        cursor.execute(f'GRANT SELECT ON {world["cash_views"]} TO {q(owner)}')
        with as_role(cursor, q, owner):
            cursor.execute(f'CREATE VIEW {target} AS SELECT cash_shift_id,variance FROM {world["cash_views"]}')
            # install_views installed default SELECT grants before this CREATE.
            # The denied reader must be excluded in the original fixture ACL.
            cursor.execute(f'REVOKE ALL ON {target} FROM {q(world["roles"]["excluded"])}')
            cursor.execute(f'GRANT SELECT (variance) ON {target} TO {q(world["roles"]["column_reader"])}')
            cursor.execute(f'GRANT SELECT ON {target} TO {q(world["roles"]["delegate"])} WITH GRANT OPTION')
            cursor.execute(f'COMMENT ON COLUMN {target}.variance IS %s', ['saved cash variance'])
        with as_role(cursor, q, world['roles']['delegate']):
            cursor.execute(f'GRANT SELECT ON {target} TO {q(world["roles"]["leaf"])}')
    world['cash_dependency'] = target
    _refused(world, 'excluded', f'SELECT * FROM {target}')


@pytest.mark.parametrize('schemas_present', [True, False])
def test_real_callbacks_sync_cash_variance_as_supported_non_superuser(monkeypatch, schemas_present):
    from decimal import Decimal

    with historical_money('shop', schemas_present=schemas_present) as world:
        if schemas_present:
            install_views(world)
        enable_migrator_sync(world)
        install_cash_sessions(world, create_views=schemas_present, sync_owners=True)
        with connection.cursor() as cursor:
            for key in ('owner', 'powner'):
                cursor.execute('SELECT has_schema_privilege(%s,%s,\'USAGE\'), '
                               'has_schema_privilege(%s,%s,\'CREATE\'), '
                               'has_schema_privilege(%s,%s,\'USAGE WITH GRANT OPTION\')',
                               [world['sync_roles'][key], world['schemas']['tables']] * 3)
                assert cursor.fetchone() == (True, False, False)
                cursor.execute('SELECT has_table_privilege(%s,%s,\'SELECT\'), '
                               'has_table_privilege(%s,%s,\'SELECT WITH GRANT OPTION\')',
                               [world['sync_roles'][key], world['cash_table']] * 2)
                assert cursor.fetchone() == (True, False)
            for role in (world['sync_roles']['reader'], world['sync_roles']['preader'],
                         *(world['roles'][key] for key in ('tenant', 'platform', 'column_reader', 'leaf', 'excluded'))):
                cursor.execute('SELECT has_schema_privilege(%s,%s,\'USAGE\'), '
                               'has_table_privilege(%s,%s,\'SELECT\')',
                               [role, world['schemas']['tables'], role, world['cash_table']])
                assert cursor.fetchone() == (False, False)
        if schemas_present:
            _cash_dependency(world)
        else:
            assert {row[1] for row in _schema_metadata(world)} == {
                world['schemas']['tables'], world['schemas']['external'],
            }
        # Bound the catalogue to its REAL cash-session definition. All sync DDL,
        # privileges, renderer gates and callbacks still execute their real code.
        monkeypatch.setattr(db_sync, 'installed_views', lambda: [world['cash_definition']])
        before = {row['target']: row for row in metadata(world)}
        defaults = _defaults(world)
        results, real_sync = [], db_sync.sync

        def observe(using, **kwargs):
            result = real_sync(using, **kwargs)
            results.append((result.state, result.reason, result.failed))
            return result

        monkeypatch.setattr(db_sync, 'sync', observe)
        with migrating(world):
            with connection.cursor() as cursor:
                cursor.execute('SELECT rolsuper,rolcreaterole,rolinherit,rolbypassrls '
                               'FROM pg_roles WHERE rolname=current_user')
                assert cursor.fetchone() == (False, True, False, False)
                for key in ('owner', 'powner'):
                    cursor.execute("SELECT pg_has_role(current_user,%s,'USAGE'),pg_has_role(current_user,%s,'SET')",
                                   [world['sync_roles'][key]] * 2)
                    assert cursor.fetchone() == (False, True)
            with CaptureQueriesContext(connection) as queries:
                db_sync.pre_migrate_drop(None, using=connection.alias, plan=[(world['step'], False)])
            assert [row['sql'] for row in queries.captured_queries if row['sql'].lstrip().upper().startswith('DROP ')] == []
            assert {row['target']: row for row in metadata(world)} == before
            with connection.schema_editor() as editor:
                world['step'].apply(world['state'].clone(), editor)
            _money(world, world['state'], {(op.model_name, op.name) for op in world['changed']})
            # Full relacl/attacl (including grantors/order), before sync can run.
            assert {row['target']: row for row in metadata(world)} == before
            assert _defaults(world) == defaults
            if schemas_present:
                _refused(world, 'excluded', f'SELECT * FROM {world["cash_dependency"]}')
            db_sync.post_migrate_sync(None, using=connection.alias)
        assert results == [('synced', '', {})]
        after = {row['target']: row for row in metadata(world)}
        assert {target: after[target] for target in before} == before
        if not schemas_present:
            _cash_dependency(world)
        stable = {row['target']: row for row in metadata(world)}
        with connection.cursor() as cursor:
            cursor.execute('SELECT to_regclass(name)::oid FROM unnest(%s::text[]) name', [list(stable)])
            identities = cursor.fetchall()
        with migrating(world):
            for _ in range(2):
                assert observe(connection.alias, force=True).failed == {}
                assert {row['target']: row for row in metadata(world)} == stable
                assert _defaults(world) == defaults
                _refused(world, 'excluded', f'SELECT * FROM {world["cash_dependency"]}')
            db_sync.post_migrate_sync(None, using=connection.alias)
        assert results == [('synced', '', {})] * 3 + [('unchanged', '', {})]
        assert {row['target']: row for row in metadata(world)} == stable
        assert _defaults(world) == defaults
        with connection.cursor() as cursor:
            cursor.execute('SELECT to_regclass(name)::oid FROM unnest(%s::text[]) name', [list(stable)])
            assert cursor.fetchall() == identities
        assert_cash_readers(world)
        assert_variance_type(world, 'numeric(13,3)')
        _select(world, 'leaf', f'SELECT * FROM {world["cash_dependency"]}', [(1, Decimal('12.35'))])
        _select(world, 'column_reader', f'SELECT variance FROM {world["cash_dependency"]}', [(Decimal('12.35'),)])
        _refused(world, 'column_reader', f'SELECT cash_shift_id FROM {world["cash_dependency"]}')
        _refused(world, 'excluded', f'SELECT * FROM {world["cash_dependency"]}')
        for switch in ('analytics', 'shop'):
            with public_support_data():
                world['own'].enabled_modules = ['shop'] if switch == 'analytics' else ['analytics']
                world['own'].save(update_fields=['enabled_modules'])
            _select(world, 'tenant', f'SELECT * FROM {world["cash_views"]}', [])
            _select(world, 'leaf', f'SELECT * FROM {world["cash_dependency"]}', [])
            with public_support_data():
                world['own'].enabled_modules = ['analytics', 'shop']
                world['own'].save(update_fields=['enabled_modules'])
            assert_cash_readers(world)
            _select(world, 'leaf', f'SELECT * FROM {world["cash_dependency"]}', [(1, Decimal('12.35'))])


def test_sync_replaces_existing_view_in_place_without_acl_or_metadata_drift():
    with historical_money('shop') as world:
        install_views(world)
        before = metadata(world)
        base = next(row for row in before if row['target'] == world['base'])
        defaults = _defaults(world)
        with migrating(world), connection.cursor() as cursor:
            cursor.execute('SELECT to_regclass(%s)::oid', [world['base']])
            oid = cursor.fetchone()[0]
            db_ddl.create_view(cursor, base['schema'], base['name'], base['sql'],
                               base['owner'], world['roles']['tenant'])
            cursor.execute('SELECT to_regclass(%s)::oid', [world['base']])
            assert cursor.fetchone() == (oid,)
        assert metadata(world) == before
        assert _defaults(world) == defaults
        assert_readers(world)


def test_sync_incompatible_output_shape_refuses_without_losing_any_objects():
    with historical_money('shop') as world:
        install_views(world)
        before = metadata(world)
        with pytest.raises(DatabaseError) as error, transaction.atomic(), migrating(world):
            with connection.cursor() as cursor:
                db_ddl.create_view(cursor, world['schemas']['views'], 'z_base', 'SELECT 0 AS only_column',
                                   world['roles']['owner'], world['roles']['tenant'])
        assert error.value.__cause__.pgcode == '42P16'
        assert metadata(world) == before
        assert_readers(world)


def test_new_sync_view_revokes_default_grantee_before_granting_reader():
    with historical_money('shop') as world:
        install_views(world)
        target = 'spaceworks_analytics.fresh'
        owner, reader = world['roles']['owner'], world['roles']['tenant']
        with migrating(world), connection.cursor() as cursor:
            db_ddl.create_view(cursor, world['schemas']['views'], 'fresh', 'SELECT 1 AS id', owner, reader)
            cursor.execute("SELECT acldefault('r',oid)::text FROM pg_roles WHERE rolname=%s", [owner])
            expected = cursor.fetchone()[0][:-1] + f',{reader}=r/{owner}' + '}'
            cursor.execute('SELECT relacl::text FROM pg_class WHERE oid=to_regclass(%s)', [target])
            assert cursor.fetchone() == (expected,)
            cursor.execute('SELECT attname,attacl::text FROM pg_attribute WHERE attrelid=to_regclass(%s) '
                           'AND attnum>0 ORDER BY attnum', [target])
            assert cursor.fetchall() == [('id', None)]
        _select(world, 'tenant', f'SELECT * FROM {target}', [(1,)])
        _refused(world, 'excluded', f'SELECT * FROM {target}')


@pytest.mark.parametrize('object_name', ['base', 'material'])
def test_sync_refuses_unexpected_owner_or_object_kind_before_ddl(object_name):
    with historical_money('shop') as world:
        install_views(world)
        before = metadata(world)
        item = next(row for row in before if row['target'] == world[object_name])
        with CaptureQueriesContext(connection) as queries:
            with pytest.raises(RuntimeError) as error, migrating(world), connection.cursor() as cursor:
                db_ddl.create_view(cursor, item['schema'], item['name'], 'SELECT 1 AS id',
                                   world['roles']['other_owner'], world['roles']['tenant'])
        actual = (item['owner'], item['kind'], item['options'])
        assert str(error.value) == f"Cannot replace analytics view with unexpected owner/kind: {item['target']} {actual!r}"
        assert [row['sql'] for row in queries.captured_queries if row['sql'].lstrip().upper().startswith('DROP ')] == []
        assert metadata(world) == before

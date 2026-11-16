"""Isolated pre-thousandths tables; no shared migration graph or recorder changes."""
from contextlib import contextmanager
from decimal import Decimal
from importlib import import_module
from uuid import uuid4

from django.db import connection, migrations, models, transaction
from django.db.migrations.loader import MigrationLoader
from django.db.migrations.state import ModelState, ProjectState

from apps.analytics.migration_acl import as_role
from apps.analytics.migration_support import MONEY_MIGRATIONS
from apps.analytics.migration_views import capture
from apps.analytics.catalogue.render import render, SPACE
from apps.analytics.catalogue.types import View, Col
from apps.makerspaces.models import Makerspace
from apps.tenant_rls.models import FixedRoleScope


@contextmanager
def public_support_data():
    """Keep live ORM support rows out of the historical table search path."""
    with connection.cursor() as cursor:
        cursor.execute("SELECT current_setting('search_path')")
        previous = cursor.fetchone()[0]
        cursor.execute('SET LOCAL search_path TO public')
    try:
        yield
    finally:
        with connection.cursor() as cursor:
            cursor.execute("SELECT set_config('search_path',%s,true)", [previous])


@contextmanager
def historical_money(app, *, schemas_present=True):
    """Materialize only the columns read by the nine real money operations.

    Fields come from each migration's actual prerequisite ModelState (the 0.9.3
    two-decimal contract), not today's model definitions or a reverse migration.
    All DDL, roles, grants and data roll back when the fixture finishes.
    """
    q = connection.ops.quote_name
    suffix = uuid4().hex[:12]
    schemas = {key: f'cx1_{key}_{suffix}' for key in ('tables', 'views', 'external', 'platform')}
    schemas.update(views='spaceworks_analytics', platform='spaceworks_analytics_platform')
    roles = {key: f'cx1_{key}_{suffix}' for key in ('migrator', 'owner', 'other_owner', 'tenant', 'platform',
                                                'column_reader', 'delegate', 'leaf', 'excluded')}
    module = import_module(f'apps.{app}.migrations.{MONEY_MIGRATIONS[app]}_money_three_decimals')
    step = module.Migration(f'{MONEY_MIGRATIONS[app]}_money_three_decimals', app)
    full = MigrationLoader(connection).project_state(step.dependencies)
    changed = [operation for operation in step.operations if isinstance(operation, migrations.AlterField)]
    states = {}
    for operation in changed:
        key = (app, operation.model_name)
        original = full.models[key]
        if key not in states:
            states[key] = ModelState(app, original.name, [('id', models.BigAutoField(primary_key=True))],
                                    options={'db_table': original.options.get('db_table', '_'.join(key))})
        states[key].fields[operation.name] = original.fields[operation.name].clone()
    state = ProjectState(states)
    prior_snapshots = dict(getattr(connection, '_analytics_migration_views', {}))
    with transaction.atomic():
        try:
            with connection.cursor() as cursor:
                cursor.execute('SELECT current_user')
                original_user = cursor.fetchone()[0]
                cursor.execute("SELECT current_setting('server_version_num')::int")
                assert cursor.fetchone()[0] >= 160000
                for key, role in roles.items():
                    inheritance = 'NOINHERIT' if key == 'migrator' else 'INHERIT'
                    cursor.execute(f'CREATE ROLE {q(role)} NOLOGIN {inheritance} NOSUPERUSER NOBYPASSRLS')
                    cursor.execute(f'GRANT {q(role)} TO {q(original_user)} WITH INHERIT FALSE, SET TRUE')
                cursor.execute("SELECT EXISTS(SELECT FROM pg_roles WHERE rolname='spaceworks_rls_fixed')")
                assert cursor.fetchone() == (True,)
                for key in ('owner', 'tenant', 'column_reader', 'delegate', 'leaf'):
                    cursor.execute(f'GRANT spaceworks_rls_fixed TO {q(roles[key])}')
                for role in roles.values():
                    if role != roles['migrator']:
                        cursor.execute(f"GRANT {q(role)} TO {q(roles['migrator'])} WITH INHERIT FALSE, SET TRUE")
                for schema in (*schemas.values(), 'spaceworks_analytics_admin'):
                    if schema in ('spaceworks_analytics', 'spaceworks_analytics_platform'):
                        cursor.execute('SELECT oid FROM pg_namespace WHERE nspname=%s', [schema])
                        if cursor.fetchone():
                            cursor.execute(f'ALTER SCHEMA {q(schema)} RENAME TO {q("cx1_saved_" + schema + suffix)}')
                        if not schemas_present:
                            continue
                    if schema == 'spaceworks_analytics_admin':
                        cursor.execute('SELECT oid FROM pg_namespace WHERE nspname=%s', [schema])
                        if cursor.fetchone():
                            cursor.execute(f'ALTER SCHEMA {q(schema)} RENAME TO {q("cx1_saved_admin_" + suffix)}')
                        continue
                    cursor.execute(f"CREATE SCHEMA {q(schema)} AUTHORIZATION {q(roles['migrator'])}")
                    for key in ('owner', 'other_owner'):
                        cursor.execute(f'GRANT USAGE,CREATE ON SCHEMA {q(schema)} TO {q(roles[key])}')
                for schema in ('views', 'external'):
                    if schema == 'views' and not schemas_present:
                        continue
                    for role in ('tenant', 'column_reader', 'delegate', 'leaf', 'excluded'):
                        cursor.execute(f'GRANT USAGE ON SCHEMA {q(schemas[schema])} TO {q(roles[role])}')
                if schemas_present:
                    cursor.execute(f"GRANT USAGE ON SCHEMA {q(schemas['platform'])} TO {q(roles['platform'])}")
                cursor.execute(f"SET LOCAL search_path TO {q(schemas['tables'])}, public")
                for key, model in states.items():
                    table = q(model.options['db_table'])
                    fields = [(name, field) for name, field in model.fields.items() if name != 'id']
                    definitions = ','.join(f'{q(field.db_column or name)} numeric({field.max_digits},{field.decimal_places})'
                                           + ('' if field.null else ' NOT NULL')
                                           for name, field in fields)
                    cursor.execute(f'CREATE TABLE {table} (id bigint PRIMARY KEY,tenant_id bigint,{definitions})')
                    names = ','.join(q(field.db_column or name) for name, field in fields)
                    for pk, amount in ((1, Decimal('12.35')), (2, Decimal('99.99'))):
                        cursor.execute(f'INSERT INTO {table} (id,tenant_id,{names}) VALUES (%s,%s,'
                                       + ','.join(['%s'] * len(fields)) + ')', [pk, pk, *([amount] * len(fields))])
                    cursor.execute(f"ALTER TABLE {table} OWNER TO {q(roles['migrator'])}")
                    for owner in ('owner', 'other_owner'):
                        cursor.execute(f'GRANT SELECT ON {table} TO {q(roles[owner])}')
            yield dict(app=app, step=step, state=state, schemas=schemas, roles=roles, changed=changed,
                       original_user=original_user)
        finally:
            connection._analytics_migration_views = prior_snapshots
            transaction.set_rollback(True)


def install_support_data(world):
    roles = world['roles']
    with public_support_data():
        own = Makerspace.objects.create(name='CX1 own', slug='cx1-own-' + roles['tenant'],
                                       enabled_modules=['analytics', 'shop'])
        other = Makerspace.objects.create(name='CX1 other', slug='cx1-other-' + roles['tenant'],
                                         enabled_modules=['analytics', 'shop'])
        for role in ('tenant', 'column_reader', 'delegate', 'leaf'):
            FixedRoleScope.objects.create(role_name=roles[role], makerspace=own)
            with connection.cursor() as cursor:
                cursor.execute('GRANT EXECUTE ON FUNCTION public.spaceworks_rls_fixed_scope(text) TO '
                               + connection.ops.quote_name(roles[role]))
    world.update(own=own, other=other)


def install_views(world):
    q = connection.ops.quote_name
    schemas, roles, state = world['schemas'], world['roles'], world['state']
    operation = world['changed'][0]
    model = state.models[(world['app'], operation.model_name)]
    table = f"{q(schemas['tables'])}.{q(model.options['db_table'])}"
    column = q(operation.field.db_column or operation.name)
    target = lambda schema, name: f'{q(schemas[schema])}.{q(name)}'
    base, report = target('views', 'z_base'), target('views', 'a_report')
    external, material = target('external', 'saved_report'), target('external', 'material')
    install_support_data(world)
    own, other = world['own'], world['other']
    definition = View('cx1_money', 'shop', 'Historical money', f'FROM {table} b', 'b.tenant_id',
                      (Col('id', 'b.id', 'ID'), Col('amount', f'b.{column}', 'Money')))
    with connection.cursor() as cursor:
        cursor.execute(f'UPDATE {table} SET tenant_id=CASE id WHEN 1 THEN %s ELSE %s END', [own.pk, other.pk])
        cursor.execute(f"GRANT USAGE ON SCHEMA public TO {q(roles['owner'])}")
        cursor.execute(f"GRANT SELECT ON public.makerspaces_makerspace TO {q(roles['owner'])}")
        with as_role(cursor, q, roles['owner']):
            cursor.execute(f'CREATE VIEW {base} WITH (security_barrier=true) AS {render(definition, SPACE)}')
            cursor.execute(f'GRANT SELECT ON {base} TO {q(roles["tenant"])}')
            cursor.execute(f'GRANT SELECT (amount) ON {base} TO {q(roles["column_reader"])}')
            cursor.execute(f'GRANT SELECT ON {base} TO {q(roles["delegate"])} WITH GRANT OPTION')
            cursor.execute(f'CREATE VIEW {report} WITH (security_barrier=true) AS SELECT * FROM {base}')
            cursor.execute(f'CREATE VIEW {target("views", "column_only")} WITH (security_barrier=true,security_invoker=false) AS SELECT * FROM {base}')
            cursor.execute(f'GRANT SELECT (amount) ON {target("views", "column_only")} TO {q(roles["column_reader"])}')
            cursor.execute(f'GRANT SELECT (amount) ON {target("views", "column_only")} TO {q(roles["delegate"])} WITH GRANT OPTION')
            cursor.execute(f'CREATE VIEW {external} AS SELECT * FROM {report}')
            cursor.execute(f'GRANT SELECT ON {external} TO {q(roles["tenant"])}')
            cursor.execute(f'GRANT SELECT ON {report} TO {q(roles["other_owner"])}')
            cursor.execute(f'COMMENT ON VIEW {base} IS %s', ['view comment: λ'])
            cursor.execute(f'COMMENT ON RULE "_RETURN" ON {base} IS %s', ['select rule comment'])
            cursor.execute(f'COMMENT ON COLUMN {base}.amount IS %s', ['column comment'])
            cursor.execute(f'ALTER VIEW {base} ALTER COLUMN amount SET DEFAULT 0')
            cursor.execute(f'CREATE RULE ignore_insert AS ON INSERT TO {base} DO INSTEAD NOTHING')
            cursor.execute(f'COMMENT ON RULE ignore_insert ON {base} IS %s', ['rule comment'])
            # PG16 supports view rules/triggers in their CREATE-time origin state;
            # ALTER TABLE ENABLE/DISABLE is not supported for this relkind.
            function = target('external', 'ignore_update')
            cursor.execute(f'CREATE FUNCTION {function}() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RETURN NEW; END $$')
            cursor.execute(f'CREATE TRIGGER ignore_update INSTEAD OF UPDATE ON {base} '
                           f'FOR EACH ROW EXECUTE FUNCTION {function}()')
            cursor.execute(f'COMMENT ON TRIGGER ignore_update ON {base} IS %s', ['trigger comment'])
        cursor.execute(f'ALTER VIEW {external} OWNER TO {q(roles["other_owner"])}')
        with as_role(cursor, q, roles['delegate']):
            cursor.execute(f'GRANT SELECT ON {base} TO {q(roles["leaf"])}')
            cursor.execute(f'GRANT SELECT (amount) ON {target("views", "column_only")} TO {q(roles["leaf"])}')
        with as_role(cursor, q, roles['other_owner']):
            cursor.execute(f'CREATE MATERIALIZED VIEW {material} WITH (fillfactor=80) AS '
                           f'SELECT id,{column} AS amount FROM {table} WITH NO DATA')
            cursor.execute(f'CREATE UNIQUE INDEX material_id ON {material} (id)')
            cursor.execute(f'COMMENT ON MATERIALIZED VIEW {material} IS %s', ['material comment'])
            cursor.execute(f'COMMENT ON INDEX {target("external", "material_id")} IS %s', ['index comment'])
            cursor.execute(f'CREATE VIEW {target("platform", "all_rows")} AS SELECT * FROM {table}')
            cursor.execute(f'GRANT SELECT ON {target("platform", "all_rows")} TO {q(roles["platform"])}')
        cursor.execute(f'CREATE TABLE {target("views", "unaffected_table")} (n integer)')
        cursor.execute(f'INSERT INTO {target("views", "unaffected_table")} VALUES (7)')
        cursor.execute(f'CREATE VIEW {target("views", "unaffected")} AS SELECT n FROM {target("views", "unaffected_table")}')
        cursor.execute(f'GRANT SELECT ON {target("views", "unaffected")} TO {q(roles["migrator"])}')
        for key in ('migrator', 'owner', 'other_owner'):
            # Defaults are installed AFTER views, so excluded must never acquire SELECT.
            cursor.execute(f'ALTER DEFAULT PRIVILEGES FOR ROLE {q(roles[key])} '
                           f'IN SCHEMA {q(schemas["external"])} GRANT SELECT ON TABLES TO {q(roles["excluded"])}')
            cursor.execute(f'ALTER DEFAULT PRIVILEGES FOR ROLE {q(roles[key])} '
                           f'GRANT SELECT ON TABLES TO {q(roles["excluded"])}')
    world.update(base=base, external=external, material=material, platform=target('platform', 'all_rows'),
                 unaffected=target('views', 'unaffected'), column_only=target('views', 'column_only'), own=own, other=other)


def metadata(world):
    with connection.cursor() as cursor:
        cursor.execute('SELECT c.oid FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace '
                       "WHERE n.nspname=ANY(%s) AND c.relkind IN ('v','m') ORDER BY n.nspname,c.relname",
                       [list(world['schemas'].values())])
        return [capture(cursor, connection.ops.quote_name, oid) for (oid,) in cursor.fetchall()]


def install_cash_sessions(world, *, create_views=True, sync_owners=False):
    """The real cash-session catalogue definition over prerequisite-schema amounts."""
    from dataclasses import replace
    from apps.analytics.catalogue.shop import VIEWS
    from apps.analytics.catalogue.render import PLATFORM

    q = connection.ops.quote_name
    if 'own' not in world:
        install_support_data(world)
    table = f'{q(world["schemas"]["tables"])}."shop_shopcashsession"'
    definition = replace(next(view for view in VIEWS if view.name == 'shop_cash_sessions'),
                         source=f'FROM {table} c')
    world['cash_definition'] = definition
    world['cash_table'] = table
    with connection.cursor() as cursor:
        cursor.execute(f'ALTER TABLE {table} ADD COLUMN makerspace_id bigint, ADD COLUMN status text, '
                       'ADD COLUMN currency text, ADD COLUMN opened_at timestamptz, ADD COLUMN closed_at timestamptz')
        cursor.execute(f'UPDATE {table} SET makerspace_id=CASE id WHEN 1 THEN %s ELSE %s END, '
                       "status='closed',currency='USD',opened_at='2026-01-01T00:00:00Z',"
                       "closed_at='2026-01-01T01:00:00Z'", [world['own'].pk, world['other'].pk])
        for schema, audience, owner, reader in (
            ('views', SPACE, 'owner', 'tenant'), ('platform', PLATFORM, 'other_owner', 'platform'),
        ):
            target = f'{q(world["schemas"][schema])}."shop_cash_sessions"'
            world['cash_' + schema] = target
            owner_role = world['sync_roles']['owner' if schema == 'views' else 'powner'] if sync_owners else world['roles'][owner]
            cursor.execute(f'GRANT USAGE ON SCHEMA {q(world["schemas"]["tables"])} TO {q(owner_role)}')
            cursor.execute(f'GRANT SELECT ON {table} TO {q(owner_role)}')
            if not create_views:
                continue
            cursor.execute(f'GRANT USAGE,CREATE ON SCHEMA {q(world["schemas"][schema])} TO {q(owner_role)}')
            with as_role(cursor, q, owner_role):
                cursor.execute(f'CREATE VIEW {target} WITH (security_barrier=true) AS {render(definition, audience)}')
                cursor.execute(f'GRANT SELECT ON {target} TO {q(world["roles"][reader])}')
                cursor.execute(f'REVOKE ALL ON {target} FROM {q(world["roles"]["excluded"])}')
                cursor.execute(f'COMMENT ON VIEW {target} IS %s', ['historical cash report'])


def enable_migrator_sync(world):
    """Administrative setup only; sync itself runs NOSUPERUSER with SET-only owners."""
    from apps.analytics.db_names import roles as database_roles
    from apps.tenant_rls.sql import FUNCTION_NAMES

    q = connection.ops.quote_name
    migrator = q(world['roles']['migrator'])
    with connection.cursor() as cursor:
        cursor.execute('SELECT current_database()')
        database = cursor.fetchone()[0]
        names = database_roles(database)
        cursor.execute(f'ALTER ROLE {migrator} CREATEROLE')
        cursor.execute(f'GRANT CREATE ON DATABASE {q(database)} TO {migrator}')
        for role in (*names.values(), 'spaceworks_rls_fixed'):
            cursor.execute(f'GRANT {q(role)} TO {migrator} WITH ADMIN TRUE, INHERIT FALSE, SET TRUE')
        for reader, key in (('reader', 'tenant'), ('preader', 'platform')):
            cursor.execute(f'GRANT {q(names[reader])} TO {q(world["roles"][key])}')
        cursor.execute(f'GRANT USAGE ON SCHEMA public TO {migrator} WITH GRANT OPTION')
        cursor.execute(f'GRANT SELECT ON ALL TABLES IN SCHEMA public TO {migrator} WITH GRANT OPTION')
        cursor.execute('SELECT oid::regprocedure::text FROM pg_proc WHERE pronamespace=\'public\'::regnamespace '
                       'AND proname=ANY(%s)', [list(FUNCTION_NAMES)])
        for (signature,) in cursor.fetchall():
            cursor.execute(f'GRANT EXECUTE ON FUNCTION {signature} TO {migrator} WITH GRANT OPTION')
    world['sync_roles'] = names

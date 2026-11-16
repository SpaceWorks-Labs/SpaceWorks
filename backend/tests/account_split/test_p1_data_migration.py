"""D12 cutover drops old authority; bounded historical tables avoid graph rewinds."""
from contextlib import contextmanager
from importlib import import_module
from uuid import uuid4

import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.db.migrations.state import ModelState, ProjectState

pytestmark = pytest.mark.django_db(transaction=True)


@contextmanager
def historical_tables(targets, labels):
    """Create only the migration's tables in a disposable PostgreSQL schema.

    Real historical fields, constraints, SQL and queryset operations run unchanged.
    Unused relation endpoints keep their real primary key shape. No public table or
    migration recorder is rewound, and no production trigger is disabled.
    """
    full = MigrationExecutor(connection).loader.project_state(targets)
    selected = {tuple(label.lower().split('.')) for label in labels}
    states = {key: full.models[key].clone() for key in selected}
    for model in list(states.values()):
        for field in model.fields.values():
            if not field.is_relation:
                continue
            for reference in (field.remote_field.model, getattr(field.remote_field, 'through', None)):
                if not isinstance(reference, str) or reference == 'self':
                    continue
                key = tuple(reference.lower().split('.'))
                if key in states:
                    continue
                source = full.models[key]
                pk_name, pk = next((name, field) for name, field in source.fields.items() if field.primary_key)
                states[key] = ModelState(key[0], source.name, [(pk_name, pk.clone())],
                                         options={'db_table': source.options.get('db_table', '_'.join(key))})
    state = ProjectState(states)
    registry = state.apps
    schema = 'ci_migration_' + uuid4().hex
    quote = connection.ops.quote_name
    with connection.cursor() as cursor:
        cursor.execute('SHOW search_path')
        original = cursor.fetchone()[0]
        cursor.execute(f'CREATE SCHEMA {quote(schema)}')
        cursor.execute(f'SET search_path TO {quote(schema)}, public')
    try:
        with connection.schema_editor() as editor:
            for model in registry.get_models():
                editor.create_model(model)
        yield registry
    finally:
        with connection.cursor() as cursor:
            cursor.execute('SELECT set_config(%s, %s, false)', ['search_path', original])
            cursor.execute(f'DROP SCHEMA {quote(schema)} CASCADE')


def test_dev_data_classification_and_staff_role_stripping():
    target = [('accounts', '0031_platformloginmethods_provider_switches'),
              ('makerspaces', '0096_enable_existing_presence'),
              ('machines', '0028_drop_role_machine_scope')]
    labels = ['accounts.User', 'makerspaces.Makerspace', 'makerspaces.MakerspaceRole',
              'makerspaces.MakerspaceMembership', 'makerspaces.MembershipAdditionalRole',
              'machines.MembershipMachineTypeScope']
    with historical_tables(target, labels) as state:
        User = state.get_model('accounts', 'User')
        Space = state.get_model('makerspaces', 'Makerspace')
        Role = state.get_model('makerspaces', 'MakerspaceRole')
        Membership = state.get_model('makerspaces', 'MakerspaceMembership')
        Additional = state.get_model('makerspaces', 'MembershipAdditionalRole')
        root = User.objects.create(username='migration-root', is_superuser=True, role='superadmin')
        mixed = User.objects.create(username='migration-mixed', role='space_manager')
        space = Space.objects.create(name='Migration', slug='migration')
        member, handover, inventory = [Role.objects.create(makerspace=space, name=slug, slug=slug,
            is_default=True, is_protected=True, granted_actions=[]) for slug in ('member', 'handover', 'inventory_manager')]
        membership = Membership.objects.create(user=mixed, makerspace=space, assigned_role=handover, role='handover')
        Additional.objects.create(membership=membership, role=inventory)
        Membership.objects.create(user=root, makerspace=space, assigned_role=member, role='custom')
        migration = import_module('apps.accounts.migrations.0032_account_context')
        step = migration.Migration('0032_account_context', 'accounts')
        with connection.schema_editor() as editor:
            state = step.apply(ProjectState.from_apps(state), editor).apps
        User = state.get_model('accounts', 'User')
        Membership = state.get_model('makerspaces', 'MakerspaceMembership')
        Additional = state.get_model('makerspaces', 'MembershipAdditionalRole')
        assert User.objects.get(pk=root.pk).account_kind == 'platform'
        assert User.objects.get(pk=mixed.pk).account_kind == 'member'
        assert not Membership.objects.filter(user_id=root.pk).exists()
        after = Membership.objects.get(pk=membership.pk)
        assert after.user_id == mixed.pk and after.assigned_role_id == member.pk and after.role == 'custom'
        assert not Additional.objects.exists()

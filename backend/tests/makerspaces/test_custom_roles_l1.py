from importlib import import_module

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.db.models.deletion import ProtectedError

from tests.accounts.account_factories import make_staff

from apps.accounts.models import User
from apps.makerspaces import roles
from apps.makerspaces.role_catalog import ROLE_CATALOG
from apps.makerspaces.models import Makerspace, MakerspaceMembership, MakerspaceRole


LEGACY_ROLE_VALUES = [definition[0] for definition in roles.DEFAULT_ROLE_DEFINITIONS]
# What migration 0039 seeded, which is not what is seeded today and must not be derived
# from the current definitions. Both extras were retired later without rewriting history:
# `print_manager` by 0046 and `guest_admin` by 0052/0053, and 0039 still creates them when
# the round-trip below replays it. `guest_admin` is spelled as a raw string on purpose --
# it is no longer an enum member, and a historical migration deals in stored values anyway.
HISTORICAL_ROLE_VALUES = ["space_manager", "inventory_manager", "machine_manager", "print_manager", "guest_admin"]


def make_user(username):
    return User.objects.create_user(username=username, password="password")


def assert_default_roles(makerspace):
    actual = {
        role.legacy_role: role
        for role in MakerspaceRole.objects.filter(makerspace=makerspace)
    }
    assert set(actual) == set(LEGACY_ROLE_VALUES) | {None}
    for legacy_role, name, granted_actions in roles.DEFAULT_ROLE_DEFINITIONS:
        role = actual[legacy_role]
        assert role.name == name
        assert role.slug == legacy_role
        assert role.granted_actions == sorted(granted_actions)
        assert role.is_default is True
        assert role.is_protected is True
    member = actual[None]
    assert member.name == "Member"
    assert member.slug == "member"
    assert member.granted_actions == []
    assert member.is_default is True
    assert member.is_protected is True


@pytest.mark.django_db(transaction=True)
def test_new_makerspace_gets_protected_default_roles():
    makerspace = Makerspace.objects.create(name="New roles", slug="new-roles")

    assert_default_roles(makerspace)


@pytest.mark.django_db(transaction=True)
def test_ensure_default_roles_is_idempotent():
    makerspace = Makerspace.objects.create(name="Idempotent roles", slug="idempotent-roles")

    roles.ensure_default_roles(makerspace)
    roles.ensure_default_roles(makerspace)

    # Every catalogue role (decided set: ROLE_CATALOG, 9 staff roles) plus the Member role.
    assert MakerspaceRole.objects.filter(makerspace=makerspace).count() == len(ROLE_CATALOG)
    assert_default_roles(makerspace)


@pytest.mark.django_db(transaction=True)
def test_seed_and_backfill_migration_round_trip(monkeypatch):
    from_target = [("makerspaces", "0037_makerspace_mattermost_webhook_url_and_more")]
    schema_target = [("makerspaces", "0038_makerspace_roles")]
    target = [("makerspaces", "0039_seed_and_backfill_roles")]
    executor = MigrationExecutor(connection)
    from django.db import migrations
    operation = executor.loader.disk_migrations[("makerspaces", "0092_fixed_roles_data")].operations[0]
    monkeypatch.setattr(operation, "reverse_code", migrations.RunPython.noop)
    makerspace_id = None

    # Build the users BEFORE rewinding. Rewinding makerspaces to 0037 cascade-unapplies
    # 107 migrations, taking accounts back to 0017, so the CURRENT User model cannot be
    # inserted afterwards -- and the historical model cannot either without supplying
    # every column that later migrations made nullable. This passed for as long as
    # accounts 0018-0021 only added new TABLES; accounts/0022 added a User COLUMN and
    # broke it. Creating the rows first is immune to any future column addition.
    users = [make_user(f"migration-role-{index}") for index in range(len(HISTORICAL_ROLE_VALUES))]

    try:
        executor.migrate(from_target)
        old_apps = executor.loader.project_state(from_target).apps
        OldMakerspace = old_apps.get_model("makerspaces", "Makerspace")
        OldMembership = old_apps.get_model("makerspaces", "MakerspaceMembership")
        makerspace = OldMakerspace.objects.create(
            name="Migrated roles", slug="migrated-roles"
        )
        makerspace_id = makerspace.id
        memberships = {}
        for index, legacy_role in enumerate(HISTORICAL_ROLE_VALUES):
            user = users[index]
            membership = OldMembership.objects.create(
                makerspace_id=makerspace.id,
                user_id=user.id,
                role=legacy_role,
            )
            memberships[legacy_role] = membership.id

        executor = MigrationExecutor(connection)
        executor.migrate(target)
        new_apps = executor.loader.project_state(target).apps
        NewMakerspaceRole = new_apps.get_model("makerspaces", "MakerspaceRole")
        NewMembership = new_apps.get_model("makerspaces", "MakerspaceMembership")
        seeded = {
            role.legacy_role: role
            for role in NewMakerspaceRole.objects.filter(makerspace_id=makerspace.id)
        }
        assert set(seeded) == set(HISTORICAL_ROLE_VALUES)
        assert seeded[MakerspaceMembership.Role.PRINT_MANAGER].granted_actions == ["manage_printing"]
        # 0039 seeds ITS OWN frozen action lists; actions added to a protected default later
        # arrive through additive backfills (0069 `manage_member_cards`), never by editing
        # the historical seed.
        seed_module = import_module("apps.makerspaces.migrations.0039_seed_and_backfill_roles")
        for legacy_role, name, granted_actions in seed_module.DEFAULT_ROLE_DEFINITIONS:
            role = seeded[legacy_role]
            assert role.name == name
            assert role.slug == legacy_role
            assert role.granted_actions == sorted(granted_actions)
            assert role.is_default is True
            assert role.is_protected is True
            membership = NewMembership.objects.get(id=memberships[legacy_role])
            assert membership.assigned_role_id == role.id
        # Compare only the backfills replayed here. F6's member/finance backfill
        # needs its later organization schema and has separate migration coverage.
        import_module("apps.makerspaces.migrations.0069_member_card_actions").forwards(new_apps, None)
        import_module("apps.makerspaces.migrations.0074_manage_devices_action").forwards(new_apps, None)
        executor = MigrationExecutor(connection)
        executor.migrate(schema_target)
        schema_apps = executor.loader.project_state(schema_target).apps
        SchemaMakerspaceRole = schema_apps.get_model("makerspaces", "MakerspaceRole")
        SchemaMembership = schema_apps.get_model("makerspaces", "MakerspaceMembership")
        assert not SchemaMakerspaceRole.objects.filter(makerspace_id=makerspace.id).exists()
        for legacy_role, membership_id in memberships.items():
            membership = SchemaMembership.objects.get(id=membership_id)
            assert membership.assigned_role_id is None
            assert membership.role == legacy_role
    finally:
        # Restore the FULL migration graph forward, not just makerspaces/0039.
        # Rewinding makerspaces to 0037 cascade-unapplies migrations in other apps
        # that depend on makerspaces/0039 (e.g. encryption/0001), and migrating only
        # makerspaces forward would leave those dropped tables missing for every
        # later test in the process.
        #
        # Remove this historical fixture first: printing/0022 is fail-closed and
        # correctly rejects any unflipped makerspace while retiring its legacy
        # tables. Raw SQL avoids loading current related models whose tables are
        # intentionally absent at `schema_target`.
        if makerspace_id is not None:
            with connection.cursor() as cursor:
                cursor.execute(
                    "DELETE FROM makerspaces_makerspacemembership WHERE makerspace_id = %s",
                    [makerspace_id],
                )
                cursor.execute(
                    "DELETE FROM makerspaces_makerspacerole WHERE makerspace_id = %s",
                    [makerspace_id],
                )
                cursor.execute(
                    "DELETE FROM makerspaces_makerspace WHERE id = %s",
                    [makerspace_id],
                )
        restore = MigrationExecutor(connection)
        restore.migrate(restore.loader.graph.leaf_nodes())


@pytest.mark.django_db(transaction=True)
def test_seeded_defaults_match_frozen_rbac_mapping():
    from apps.accounts import rbac

    makerspace = Makerspace.objects.create(name="Parity roles", slug="parity-roles")
    seeded = {
        role.legacy_role: role.granted_actions
        for role in MakerspaceRole.objects.filter(makerspace=makerspace)
    }

    assert set(seeded) == set(LEGACY_ROLE_VALUES) | {None}
    for legacy_role, _name, actions in roles.DEFAULT_ROLE_DEFINITIONS:
        assert seeded[legacy_role] == sorted(actions)
    assert seeded[None] == []


@pytest.mark.django_db(transaction=True)
def test_assigned_builtin_is_protected_and_database_refuses_null_legacy_membership():
    makerspace = Makerspace.objects.create(name="Role constraints", slug="role-constraints")
    actor = make_staff(makerspace, username="protected-role-user", role_slug="event_manager")
    membership = MakerspaceMembership.staff_tracks.get(user=actor, makerspace=makerspace)
    role = membership.assigned_role
    with pytest.raises(ProtectedError):
        role.delete()
    with pytest.raises(IntegrityError), transaction.atomic():
        MakerspaceMembership.objects.create(
            makerspace=makerspace, user=make_user("legacy-role-user"),
            role="machine_manager", assigned_role=None,
        )
        with connection.cursor() as cursor:
            cursor.execute("SET CONSTRAINTS ALL IMMEDIATE")
    assert membership.assigned_role_id == role.pk





@pytest.mark.django_db(transaction=True)
def test_membership_clean_rejects_cross_tenant_assigned_role():
    space_a = Makerspace.objects.create(name="Tenant A", slug="tenant-a")
    space_b = Makerspace.objects.create(name="Tenant B", slug="tenant-b")
    role_b = MakerspaceRole.objects.get(makerspace=space_b, slug="event_manager")
    membership = MakerspaceMembership(
        makerspace=space_a,
        user=make_user("cross-tenant-user"),
        assigned_role=role_b,
    )
    with pytest.raises(ValidationError):
        membership.clean()


# --------------------------------------------------------------------------
# Guest Admin retired as a built-in (migration 0052).
# --------------------------------------------------------------------------

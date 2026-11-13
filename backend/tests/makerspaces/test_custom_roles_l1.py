from importlib import import_module
from types import SimpleNamespace

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, connection, transaction
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


class _Rows:
    """The few queryset calls migration 0039 makes, over plain dicts (one table)."""

    def __init__(self):
        self.rows, self.next_id = [], 1
        self.objects = self

    def all(self):
        return self

    def iterator(self):
        return iter(list(self.rows))

    def create(self, **values):
        row = SimpleNamespace(id=self.next_id, **values)
        self.next_id += 1
        self.rows.append(row)
        return row

    def update_or_create(self, defaults=None, **keys):
        for row in self.rows:
            if all(getattr(row, k) == v for k, v in keys.items()):
                for k, v in (defaults or {}).items():
                    setattr(row, k, v)
                return row, False
        return self.create(**keys, **(defaults or {})), True

    def filter(self, **conditions):
        rows = self.rows
        for key, value in conditions.items():
            if key == "assigned_role__is_default":
                rows = [r for r in rows if r.assigned_role_id is not None and value]
            else:
                rows = [r for r in rows if getattr(r, key) == value]
        return _Selection(self, rows)


class _Selection:
    def __init__(self, table, rows):
        self.table, self.rows = table, rows

    def update(self, **values):
        for row in self.rows:
            for key, value in values.items():
                setattr(row, key, value)

    def delete(self):
        self.table.rows[:] = [r for r in self.table.rows if r not in self.rows]


def test_seed_and_backfill_migration_round_trip():
    """Replay 0039's own data functions over the historical shape.

    Rewinding the real database to 0037 unapplies ~107 migrations and Django's state rebuild is
    superlinear in time and memory (it once wedged the shared test runner), and the current
    `MakerspaceRole` table refuses the retired `guest_admin`/`print_manager` rows 0039 seeds
    (`makerspacerole_fixed_catalogue`). The functions only use a handful of queryset calls, so they
    run against an in-memory registry; every assertion on what is seeded, backfilled and undone stays.
    """
    seed_module = import_module("apps.makerspaces.migrations.0039_seed_and_backfill_roles")
    spaces, role_table, memberships = _Rows(), _Rows(), _Rows()
    space = spaces.create(slug="migrated-roles")
    registry = SimpleNamespace(get_model=lambda _app, name: {
        "Makerspace": spaces, "MakerspaceRole": role_table, "MakerspaceMembership": memberships}[name])
    ids = {}
    for legacy_role in HISTORICAL_ROLE_VALUES:
        ids[legacy_role] = memberships.create(makerspace_id=space.id, role=legacy_role, assigned_role_id=None).id

    seed_module.forwards(registry, None)
    seeded = {role.legacy_role: role for role in role_table.rows if role.makerspace_id == space.id}
    assert set(seeded) == set(HISTORICAL_ROLE_VALUES)
    assert seeded["print_manager"].granted_actions == ["manage_printing"]
    # 0039 seeds ITS OWN frozen action lists; actions added to a protected default later arrive
    # through additive backfills (0069 `manage_member_cards`), never by editing the historical seed.
    for legacy_role, name, granted_actions in seed_module.DEFAULT_ROLE_DEFINITIONS:
        role = seeded[legacy_role]
        assert role.name == name
        assert role.slug == legacy_role
        assert role.granted_actions == sorted(granted_actions)
        assert role.is_default is True
        assert role.is_protected is True
        membership = next(m for m in memberships.rows if m.id == ids[legacy_role])
        assert membership.assigned_role_id == role.id
    seed_module.forwards(registry, None)  # replay is idempotent
    assert len(role_table.rows) == len(HISTORICAL_ROLE_VALUES)

    seed_module.backwards(registry, None)
    assert not role_table.rows
    for legacy_role, membership_id in ids.items():
        membership = next(m for m in memberships.rows if m.id == membership_id)
        assert membership.assigned_role_id is None
        assert membership.role == legacy_role


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

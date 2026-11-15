"""Historical project-state seed checks without database migration rewinds."""

from importlib import import_module
from types import SimpleNamespace

import pytest
from django.db import connection
from django.db.migrations.loader import MigrationLoader
from django.db.models.deletion import ProtectedError

from apps.audit.models import AuditLog
from apps.makerspaces.models import MakerspaceRole
from apps.makerspaces.roles import ensure_default_roles
from tests.return_helpers import make_member, make_space

pytestmark = pytest.mark.django_db
TARGET = ("makerspaces", "0156_fundraising_role_550")


def migration_context():
    loader = MigrationLoader(connection)
    state = loader.project_state(TARGET)
    return state.apps, SimpleNamespace(connection=connection)


def test_leaf_migration_seeds_existing_spaces_once_and_reverse_preserves_preexisting_role():
    missing = make_space("cx14-seed-missing")
    preserved = make_space("cx14-seed-existing")
    MakerspaceRole.objects.filter(makerspace=missing, slug="fundraising").delete()
    original = MakerspaceRole.objects.get(makerspace=preserved, slug="fundraising")
    apps, editor = migration_context()
    migration = import_module("apps.makerspaces.migrations.0156_fundraising_role_550")
    assert ("makerspaces", "0155_storagequotareservation") in migration.Migration.dependencies
    migration.forwards(apps, editor)
    migration.forwards(apps, editor)
    seeded = MakerspaceRole.objects.get(makerspace=missing, slug="fundraising")
    assert (seeded.name, seeded.legacy_role, seeded.granted_actions, seeded.is_default, seeded.is_protected) == (
        "Fundraising", "fundraising", ["manage_donations"], True, True)
    assert MakerspaceRole.objects.filter(makerspace=missing, slug="fundraising").count() == 1
    assert AuditLog.objects.filter(makerspace=missing, action="staff.roles_migrated",
                                   meta__source="migration:makerspaces.0156", meta__direction="forward").count() == 1
    migration.backwards(apps, editor)
    assert not MakerspaceRole.objects.filter(pk=seeded.pk).exists()
    assert MakerspaceRole.objects.filter(pk=original.pk).exists()
    assert AuditLog.objects.filter(makerspace=missing, action="staff.roles_migrated",
                                   meta__source="migration:makerspaces.0156", meta__direction="reverse").count() == 1


def test_reverse_refuses_an_in_use_seeded_role():
    space = make_space("cx14-seed-used")
    MakerspaceRole.objects.filter(makerspace=space, slug="fundraising").delete()
    apps, editor = migration_context()
    migration = import_module("apps.makerspaces.migrations.0156_fundraising_role_550")
    migration.forwards(apps, editor)
    make_member("cx14-seed-holder", space, membership_role="fundraising")
    with pytest.raises(ProtectedError):
        migration.backwards(apps, editor)
    assert MakerspaceRole.objects.filter(makerspace=space, slug="fundraising").count() == 1


def test_new_space_and_repeated_bootstrap_have_one_protected_fundraising_role():
    space = make_space("cx14-seed-new")
    for _ in range(2):
        ensure_default_roles(space)
    role = MakerspaceRole.objects.get(makerspace=space, slug="fundraising")
    assert role.is_default is True and role.is_protected is True
    assert role.granted_actions == ["manage_donations"]
    assert MakerspaceRole.objects.filter(makerspace=space, slug="fundraising").count() == 1

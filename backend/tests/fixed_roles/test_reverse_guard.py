"""0092 refuses reversal when authority relies on the fixed catalogue."""
import pytest
from django.db import connection
from django.db.migrations.exceptions import IrreversibleError

from apps.makerspaces.migration_support.fixed_roles_reverse import reverse_fixed_roles
from tests.fixed_roles.migration_helpers import old_database, historical_world, upgrade

pytestmark = pytest.mark.django_db(transaction=True)


def test_rollback_refuses_once_a_membership_holds_an_additional_role(old_database):
    world = historical_world(old_database)
    registry = upgrade(old_database)
    role = registry.get_model("makerspaces", "MakerspaceRole")
    with pytest.raises(IrreversibleError, match="restore the pre-upgrade backup"):
        reverse_fixed_roles(registry, connection.alias)
    assert role.objects.filter(makerspace_id=world["space"].pk, slug="event_manager").exists()


def test_rollback_of_an_unused_catalogue_drops_only_the_new_builtins(old_database):
    space = old_database.get_model("makerspaces", "Makerspace").objects.create(
        name="Unused catalogue", slug="reverse-guard-allows")
    registry = upgrade(old_database)
    reverse_fixed_roles(registry, connection.alias)
    slugs = set(registry.get_model("makerspaces", "MakerspaceRole").objects.filter(
        makerspace_id=space.pk).values_list("slug", flat=True))
    assert slugs == {"space_manager", "inventory_manager", "machine_manager", "member"}

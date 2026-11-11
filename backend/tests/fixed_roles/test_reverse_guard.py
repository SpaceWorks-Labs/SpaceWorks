"""0089 rolls back only when nothing relies on the fixed catalogue yet."""
import pytest
from django.db import connection
from django.db.migrations.exceptions import IrreversibleError
from django.db.migrations.executor import MigrationExecutor

from apps.makerspaces.models import MakerspaceRole
from tests.fixed_roles.helpers import assign_builtin_roles
from tests.return_helpers import make_space, make_member

BEFORE_DATA = [("makerspaces", "0091_fixed_roles_schema")]


@pytest.mark.django_db(transaction=True)
def test_rollback_refuses_once_a_membership_holds_an_additional_role():
    space = make_space("reverse-guard-refuses")
    assign_builtin_roles(make_member("reverse-guard-holder", space, membership_role="inventory_manager"), space, "inventory_manager", "event_manager")
    leaves = MigrationExecutor(connection).loader.graph.leaf_nodes()
    try:
        with pytest.raises(IrreversibleError):
            MigrationExecutor(connection).migrate(BEFORE_DATA)
    finally:
        # Later migrations were already unapplied before 0089 refused; restore them.
        MigrationExecutor(connection).migrate(leaves)
    assert MakerspaceRole.objects.filter(makerspace=space, slug="event_manager").exists()


@pytest.mark.django_db(transaction=True)
def test_rollback_of_an_unused_catalogue_drops_only_the_new_builtins():
    space = make_space("reverse-guard-allows")
    executor = MigrationExecutor(connection)
    leaves = executor.loader.graph.leaf_nodes()
    try:
        executor.migrate(BEFORE_DATA)
        old_apps = executor.loader.project_state(BEFORE_DATA).apps
        slugs = set(old_apps.get_model("makerspaces", "MakerspaceRole").objects
                    .filter(makerspace_id=space.pk).values_list("slug", flat=True))
        assert slugs == {"space_manager", "inventory_manager", "machine_manager", "member"}
    finally:
        MigrationExecutor(connection).migrate(leaves)

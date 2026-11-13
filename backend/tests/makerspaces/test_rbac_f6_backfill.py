from importlib import import_module

import pytest
from django.apps import apps
from django.db import IntegrityError, connection, transaction

from apps.accounts import rbac
from apps.makerspaces.models import MakerspaceMembership, MakerspaceRole
from apps.makerspaces.roles import ensure_default_roles
from tests.return_helpers import make_member, make_space
from tests.fixed_roles.migration_helpers import old_database

pytestmark = pytest.mark.django_db
NEW = {rbac.Action.MANAGE_MEMBERS, rbac.Action.VIEW_FINANCE, rbac.Action.RECORD_PAYMENT}


@pytest.mark.django_db(transaction=True)
def test_backfill_is_additive_idempotent_and_covers_custom_admin_roles(old_database):
    MakerspaceRole = old_database.get_model("makerspaces", "MakerspaceRole")
    space = old_database.get_model("makerspaces", "Makerspace").objects.create(name="F6", slug="f6-backfill")
    manager_role = MakerspaceRole.objects.create(makerspace=space, name="Space Manager", slug="space_manager",
        is_default=True, is_protected=True, legacy_role="space_manager")
    MakerspaceRole.objects.create(makerspace=space, name="Inventory Manager", slug="inventory_manager",
        is_default=True, is_protected=True, legacy_role="inventory_manager", granted_actions=["edit_inventory"])
    manager_role.granted_actions = [rbac.Action.MANAGE_MAKERSPACE, rbac.Action.VIEW_AUDIT]
    manager_role.save(update_fields=["granted_actions"])
    custom = MakerspaceRole.objects.create(
        makerspace=space, name="Admin", slug="admin", granted_actions=["manage_makerspace"],
    )
    inventory = MakerspaceRole.objects.get(makerspace=space, slug="inventory_manager")
    before = list(inventory.granted_actions)
    migration = import_module("apps.makerspaces.migrations.0078_member_finance_actions")
    assert ("makerspaces", "0077_makerspace_location_profile") in migration.Migration.dependencies
    assert ("organizations", "0003_organization_presentation_and_governance") in migration.Migration.dependencies
    for _ in range(2):
        migration.forwards(old_database, connection.schema_editor())
    manager_role.refresh_from_db()
    custom.refresh_from_db()
    inventory.refresh_from_db()
    assert set(manager_role.granted_actions) == NEW | {"manage_makerspace", "view_audit"}
    assert set(custom.granted_actions) == NEW | {"manage_makerspace"}
    assert inventory.granted_actions == before


def test_space_manager_actions_require_a_valid_primary_and_null_legacy_is_refused():
    space = make_space("f6-defaults")
    ensure_default_roles(space)
    # Every built-in of the fixed catalogue (ROLE_CATALOG, ten roles in 0.12.0) is seeded protected;
    # the old literal 7 predates the later built-ins.
    from apps.makerspaces.role_catalog import ROLE_CATALOG
    assert set(MakerspaceRole.objects.filter(makerspace=space, is_protected=True).values_list("slug", flat=True)) == {
        role.slug for role in ROLE_CATALOG}
    assert NEW <= set(MakerspaceRole.objects.get(makerspace=space, slug="space_manager").granted_actions)
    actor = make_member("f6-legacy", space)
    # make_member gives a Space Manager, i.e. a staff-track row (decision 63); the default and reverse
    # managers are community-only, so read and corrupt the staff row through staff_tracks.
    membership = MakerspaceMembership.staff_tracks.get(user=actor, makerspace=space)
    with pytest.raises(IntegrityError), transaction.atomic():
        MakerspaceMembership.staff_tracks.filter(pk=membership.pk).update(assigned_role=None)
        membership.refresh_from_db()
        assert rbac.actions_for_membership(membership) == set()
        with connection.cursor() as cursor:
            cursor.execute("SET CONSTRAINTS ALL IMMEDIATE")
    membership.refresh_from_db()
    assert NEW <= rbac.actions_for_membership(membership)
    assert rbac.Action.MANAGE_MEMBER_CARDS in rbac.expand_implied_actions({"manage_members"})
    assert "manage_members" not in rbac.expand_implied_actions({"manage_makerspace"})




def test_organization_admin_backfill_preserves_actions_without_widening_reach():
    from apps.organizations.models import Organization, OrganizationMakerspace, OrganizationMembership
    from tests.return_helpers import make_user

    space = make_space("f6-org-owned")
    other = make_space("f6-org-unlinked")
    organization = Organization.objects.create(name="Parent", slug="f6-parent")
    OrganizationMakerspace.objects.create(organization=organization, makerspace=space, relationship="owner")
    actor = make_user("f6-org-admin", access_status="active")
    grant = OrganizationMembership.objects.create(
        organization=organization, user=actor, granted_actions=["manage_makerspace"],
    )
    migration = import_module("apps.makerspaces.migrations.0078_member_finance_actions")
    migration.forwards(apps, connection.schema_editor())
    grant.refresh_from_db()
    assert NEW <= set(grant.granted_actions)
    for action in NEW:
        assert rbac.can(actor, action, space.pk)
        assert not rbac.can(actor, action, other.pk)

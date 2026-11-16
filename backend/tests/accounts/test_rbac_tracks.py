"""RBAC on tracks: scope unions both, authority reads staff rows, org authority is the person's."""

import pytest

from apps.accounts import rbac
from apps.makerspaces.models import Makerspace

from .ua1_helpers import community, person, platform, space, staff_row

pytestmark = pytest.mark.django_db


def test_scope_unions_both_tracks_but_actions_come_from_staff_rows():
    home, work, other = space("home"), space("work"), space("other")
    user = person("both")
    community(user, home)
    staff_row(user, work, "inventory_manager")
    assert rbac.resolve_scope(user) == {home.pk, work.pk}
    assert set(rbac.scope_by_makerspace(user, Makerspace.objects.all(), "id").values_list("pk", flat=True)) == {
        home.pk, work.pk}
    assert rbac.can(user, rbac.Action.EDIT_INVENTORY, work.pk)
    assert not rbac.can(user, rbac.Action.EDIT_INVENTORY, home.pk)
    assert rbac.makerspaces_for_action(user, rbac.Action.EDIT_INVENTORY) == {work.pk}
    assert rbac.effective_actions(user, home.pk) == set()
    assert not rbac.can(user, rbac.Action.VIEW_INVENTORY, other.pk)


def test_space_manager_identity_needs_the_staff_row():
    makerspace = space("manager")
    manager, member = person("manager"), person("member-only")
    staff_row(manager, makerspace, "space_manager")
    community(member, makerspace)
    assert rbac.is_space_manager_identity(manager, makerspace.pk)
    assert not rbac.is_space_manager_identity(member, makerspace.pk)
    assert rbac.membership_role(manager, makerspace.pk) == "space_manager"
    assert rbac.membership_role(member, makerspace.pk) is None


def test_revoked_staff_row_grants_nothing_but_community_scope_remains():
    makerspace, user = space("revoked"), person("revoked")
    community(user, makerspace)
    staff_row(user, makerspace, "event_manager", status="revoked")
    assert rbac.resolve_scope(user) == {makerspace.pk}
    assert not rbac.can(user, rbac.Action.MANAGE_EVENTS, makerspace.pk)


def test_superadmin_is_global_and_holds_no_rows():
    makerspace, root = space("root"), platform()
    assert rbac.can(root, rbac.Action.MANAGE_MAKERSPACE, makerspace.pk)
    assert rbac.is_space_manager_identity(root, makerspace.pk)


def test_organization_authority_is_the_persons():
    from apps.organizations.models import Organization, OrganizationMakerspace, OrganizationMembership

    makerspace, user = space("org-space"), person("org-member")
    organization = Organization.objects.create(name="Club", slug="club-ua1")
    OrganizationMakerspace.objects.create(organization=organization, makerspace=makerspace,
                                          relationship=OrganizationMakerspace.Relationship.AFFILIATE)
    OrganizationMembership.objects.create(
        organization=organization, user=user, status=OrganizationMembership.Status.ACTIVE,
        granted_actions=[rbac.Action.MANAGE_EVENTS])
    staff_row(user, space("unrelated"), "booking_manager")
    assert rbac.has_any_org_authority(user)
    assert rbac.can(user, rbac.Action.MANAGE_EVENTS, makerspace.pk)

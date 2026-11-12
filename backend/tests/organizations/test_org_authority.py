import pytest
from django.utils import timezone

from apps.accounts import rbac
from apps.accounts.models import User
from apps.makerspaces.models import Makerspace
from apps.organizations.models import (
    Organization,
    OrganizationMakerspace,
    OrganizationMembership,
)
from tests.fixed_roles.helpers import assign_builtin_roles


pytestmark = pytest.mark.django_db


def make_user(username, **kwargs):
    creator = (User.objects.create_superuser if kwargs.get("is_superuser")
               or kwargs.get("role") == User.Role.SUPERADMIN else User.objects.create_user)
    return creator(
        username=username,
        email=f"{username}@example.com",
        password="password",
        **kwargs,
    )


def make_makerspace(slug, **kwargs):
    return Makerspace.objects.create(name=slug.title(), slug=slug, **kwargs)


def make_organization(slug, **kwargs):
    return Organization.objects.create(name=slug.title(), slug=slug, **kwargs)


def link(organization, makerspace, relationship):
    return OrganizationMakerspace.objects.create(
        organization=organization,
        makerspace=makerspace,
        relationship=relationship,
    )


def grant(organization, user, actions, **kwargs):
    return OrganizationMembership.objects.create(
        organization=organization,
        user=user,
        granted_actions=actions,
        **kwargs,
    )


def test_org_action_reaches_every_linked_space_without_conferring_identity():
    user = make_user("org-inventory-editor")
    organization = make_organization("org-authority")
    linked = [
        make_makerspace("org-owned"),
        make_makerspace("org-managed"),
        make_makerspace("org-affiliated"),
    ]
    unlinked = make_makerspace("org-unlinked")
    for makerspace, relationship in zip(
        linked,
        (
            OrganizationMakerspace.Relationship.OWNER,
            OrganizationMakerspace.Relationship.MANAGER,
            OrganizationMakerspace.Relationship.AFFILIATE,
        ),
        strict=True,
    ):
        link(organization, makerspace, relationship)
    grant(organization, user, [rbac.Action.EDIT_INVENTORY])

    assert rbac.makerspaces_for_action(user, rbac.Action.EDIT_INVENTORY) == {
        makerspace.id for makerspace in linked
    }
    for makerspace in linked:
        assert rbac.can(user, rbac.Action.EDIT_INVENTORY, makerspace.id)
        assert rbac._membership_for(user, makerspace.id) is None
        assert rbac.membership_role(user, makerspace.id) is None
        assert not rbac.is_space_manager_identity(user, makerspace.id)
    assert not rbac.can(user, rbac.Action.EDIT_INVENTORY, unlinked.id)
    assert rbac.resolve_scope(user) == set()


def test_organization_grant_and_staff_role_union_on_one_person():
    user = make_user("local-and-org-authority")
    makerspace = make_makerspace("local-and-org-space")
    organization = make_organization("local-and-org")
    link(organization, makerspace, OrganizationMakerspace.Relationship.MANAGER)
    grant(organization, user, [rbac.Action.EDIT_INVENTORY])
    from tests.accounts.account_factories import grant_staff_role

    # U-A1: one account per person, so the staff-track row lands on the same person.
    grant_staff_role(user, makerspace, role_slug="event_manager")
    assert rbac.effective_actions(user, makerspace.id) >= {
        rbac.Action.EDIT_INVENTORY, rbac.Action.MANAGE_EVENTS}


def test_archived_linked_space_excludes_org_authority():
    user = make_user("archived-org-member")
    makerspace = make_makerspace("archived-org-space")
    organization = make_organization("archived-org")
    link(organization, makerspace, OrganizationMakerspace.Relationship.OWNER)
    grant(organization, user, [rbac.Action.EDIT_INVENTORY])
    makerspace.archived_at = timezone.now()
    makerspace.save(update_fields=["archived_at"])

    assert not rbac.can(user, rbac.Action.EDIT_INVENTORY, makerspace.id)
    assert rbac.effective_actions(user, makerspace.id) == set()
    assert rbac.makerspaces_for_action(user, rbac.Action.EDIT_INVENTORY) == set()


def test_invalid_or_inactive_org_membership_data_confers_nothing():
    cases = [
        ("suspended", True, [rbac.Action.EDIT_INVENTORY], "suspended"),
        ("inactive-org", False, [rbac.Action.EDIT_INVENTORY], "active"),
        ("malformed", True, {"edit_inventory": True}, "active"),
        (
            "forbidden",
            True,
            [rbac.Action.TRANSFER_STOCK, rbac.Action.MANAGE_STAFF],
            "active",
        ),
    ]
    for slug, organization_active, actions, status in cases:
        user = make_user(f"{slug}-org-user")
        makerspace = make_makerspace(f"{slug}-org-space")
        organization = make_organization(
            f"{slug}-org",
            is_active=organization_active,
        )
        link(organization, makerspace, OrganizationMakerspace.Relationship.MANAGER)
        grant(organization, user, actions, status=status)

        assert rbac.effective_actions(user, makerspace.id) == set()
        for action in (
            rbac.Action.EDIT_INVENTORY,
            rbac.Action.TRANSFER_STOCK,
            rbac.Action.MANAGE_STAFF,
        ):
            assert not rbac.can(user, action, makerspace.id)
            assert rbac.makerspaces_for_action(user, action) == set()


def test_org_manage_machines_is_filtered_before_implied_actions_expand():
    user = make_user("org-machine-manager")
    makerspace = make_makerspace("org-machine-space")
    organization = make_organization("org-machine-authority")
    link(organization, makerspace, OrganizationMakerspace.Relationship.MANAGER)
    grant(organization, user, [rbac.Action.MANAGE_MACHINES])

    for action in (
        rbac.Action.MANAGE_MACHINES,
        rbac.Action.MANAGE_PRINTING,
        rbac.Action.COLLECT_SERVICE_REQUEST,
    ):
        assert not rbac.can(user, action, makerspace.id)
        assert action not in rbac.effective_actions(user, makerspace.id)
        assert rbac.makerspaces_for_action(user, action) == set()


def test_admin_form_rejects_actions_rbac_would_silently_drop():
    from apps.organizations.admin import OrganizationMembershipForm

    organization = make_organization("form-validation")
    user = make_user("form-validation-user")

    for actions in (["edit_inventoryy"], ["transfer_stock"], ["manage_staff"], "nope"):
        form = OrganizationMembershipForm(
            data={
                "organization": organization.pk,
                "user": user.pk,
                "status": "active",
                "granted_actions": actions,
            }
        )
        assert not form.is_valid()
        assert "granted_actions" in form.errors

    form = OrganizationMembershipForm(
        data={
            "organization": organization.pk,
            "user": user.pk,
            "status": "active",
            "granted_actions": ["manage_printing", "edit_inventory"],
        }
    )
    assert form.is_valid(), form.errors
    assert form.cleaned_data["granted_actions"] == ["edit_inventory", "manage_printing"]


def test_deleting_an_org_membership_is_audited(monkeypatch):
    monkeypatch.setattr("apps.organizations.admin_memberships.require_recent_reauth", lambda request: None)
    from apps.audit.models import AuditLog
    from apps.organizations.admin import OrganizationMembershipAdmin
    from django.contrib.admin.sites import AdminSite
    from apps.organizations.models import OrganizationMembership as Membership

    superadmin = make_user(
        "org-delete-superadmin",
        role=User.Role.SUPERADMIN,
        is_superuser=True,
        is_staff=True,
    )
    makerspace = make_makerspace("org-delete-space")
    organization = make_organization("org-delete-org")
    link(organization, makerspace, OrganizationMakerspace.Relationship.MANAGER)
    user = make_user("org-delete-user")
    membership = grant(organization, user, [rbac.Action.EDIT_INVENTORY])

    class _Request:
        pass

    request = _Request()
    request.user = superadmin
    admin_instance = OrganizationMembershipAdmin(Membership, AdminSite())

    admin_instance.delete_model(request, membership)

    assert not Membership.objects.filter(pk=membership.pk).exists()
    assert AuditLog.objects.filter(action="organization.membership_deleted").exists()
    assert not rbac.can(user, rbac.Action.EDIT_INVENTORY, makerspace.id)

"""Shared actors and spaces for the phase-10 audit explorer tests."""
from tests.account_split.sweep_helpers import (
    configured_membership as _configured_membership,
    create_test_user as _create_test_user,
    make_role_account as _make_role_account,
)

from rest_framework.test import APIClient

from apps.accounts import rbac
from apps.accounts.models import User
from apps.makerspaces.models import Makerspace, MakerspaceMembership, MakerspaceRole
from apps.organizations.models import (
    Organization,
    OrganizationMakerspace,
    OrganizationMembership,
)


def user(username, **kwargs):
    kwargs.setdefault("access_status", User.AccessStatus.ACTIVE)
    return _create_test_user(username=username, password="pw-strong-123", **kwargs)


def space(slug):
    return Makerspace.objects.create(name=slug.title(), slug=slug)


def superadmin(username="audit-root"):
    return user(username, role=User.Role.SUPERADMIN, is_superuser=True, is_staff=True)


def member_with(makerspace, username, legacy_role):
    actor = _make_role_account(
        makerspace,
        role_slug=(MakerspaceRole.objects.get(makerspace=makerspace, legacy_role=legacy_role)).slug,
        username=username,
        password="pw-strong-123",
    )
    _configured_membership(user=actor, makerspace=makerspace)
    return actor


def custom_role_member(makerspace, username, actions):
    from tests.fixed_roles.helpers import roles_for_actions, assign_builtin_roles
    from tests.account_split.sweep_helpers import make_role_account

    roles = roles_for_actions(makerspace, actions)
    actor = make_role_account(makerspace, username=username, role_slug=roles[0].slug,
                              password="pw-strong-123", access_status="active")
    assign_builtin_roles(actor, makerspace, *(role.slug for role in roles))
    return actor


def org_auditor(makerspace, username):
    organization = Organization.objects.create(name=f"{username} org", slug=f"{username}-org")
    OrganizationMakerspace.objects.create(
        organization=organization,
        makerspace=makerspace,
        relationship=OrganizationMakerspace.Relationship.OWNER,
    )
    actor = user(username)
    OrganizationMembership.objects.create(
        organization=organization, user=actor, granted_actions=[rbac.Action.VIEW_AUDIT]
    )
    return actor


def client_for(actor):
    client = APIClient()
    client.force_authenticate(actor)
    return client

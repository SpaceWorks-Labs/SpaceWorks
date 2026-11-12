import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts import rbac
from apps.machines import member_scope_services
from apps.machines.models import MachineType
from apps.machines.models_membership_scope import MembershipMachineTypeScope
from tests.fixed_roles.helpers import assign_builtin_roles
from apps.organizations.models import (
    Organization,
    OrganizationMakerspace,
    OrganizationMembership,
)
from tests.organizations.test_org_authority import (
    grant,
    link,
    make_makerspace,
    make_organization,
    make_user,
)


pytestmark = pytest.mark.django_db


def _organization_manager(slug):
    makerspace = make_makerspace(f"{slug}-space")
    organization = make_organization(f"{slug}-org")
    actor = make_user(f"{slug}-actor")
    organization_link = link(
        organization,
        makerspace,
        OrganizationMakerspace.Relationship.MANAGER,
    )
    organization_grant = grant(
        organization,
        actor,
        [rbac.Action.MANAGE_MAKERSPACE],
    )
    return makerspace, actor, organization_link, organization_grant


def test_organization_manager_can_assign_member_machine_types():
    case = _machine_scope_case("org-scope-success")
    response = case["client"].put(case["url"], {
        "machine_type_ids": [case["machine_type"].pk],
    }, format="json")
    assert response.status_code == 200, response.data
    assert response.data["machine_type_ids"] == [case["machine_type"].pk]
    assert MembershipMachineTypeScope.objects.filter(
        membership=case["membership"], machine_type=case["machine_type"],
    ).exists()


def _machine_scope_case(slug):
    makerspace, actor, organization_link, organization_grant = (
        _organization_manager(slug)
    )
    machine_type = MachineType.objects.create(
        makerspace=makerspace,
        slug=f"{slug}-type",
        name=f"{slug} type",
    )
    target = make_user(f"{slug}-target")
    membership = assign_builtin_roles(target, makerspace, "machine_manager")
    client = APIClient()
    # The machine-scope PUT is a step-up route; record a recent proof.
    from tests.accounts.reauth_helpers import force_recent_authenticate
    force_recent_authenticate(client, actor)
    url = reverse(
        "admin-membership-machine-scope",
        args=[makerspace.pk, membership.pk],
    )
    return {
        "client": client,
        "url": url,
        "membership": membership,
        "machine_type": machine_type,
        "organization_link": organization_link,
        "organization_grant": organization_grant,
    }


def _put_scope_after_revocation(monkeypatch, case, revoke):
    original = member_scope_services.set_member_machine_scope

    def revoke_after_view_authorization(**kwargs):
        revoke()
        return original(**kwargs)

    monkeypatch.setattr(
        member_scope_services,
        "set_member_machine_scope",
        revoke_after_view_authorization,
    )
    response = case["client"].put(
        case["url"],
        {
            "machine_type_ids": [case["machine_type"].pk],
        },
        format="json",
    )
    assert response.status_code == 403
    assert not MembershipMachineTypeScope.objects.filter(membership=case["membership"]).exists()


def test_machine_scope_write_fails_when_org_grant_is_revoked_after_lookup(
    monkeypatch,
):
    case = _machine_scope_case("org-scope-grant-race")
    _put_scope_after_revocation(
        monkeypatch,
        case,
        case["organization_grant"].delete,
    )


def test_machine_scope_write_fails_when_org_link_is_revoked_after_lookup(
    monkeypatch,
):
    case = _machine_scope_case("org-scope-link-race")
    _put_scope_after_revocation(
        monkeypatch,
        case,
        case["organization_link"].delete,
    )

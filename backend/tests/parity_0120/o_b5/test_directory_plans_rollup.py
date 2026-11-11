"""O-B5: public directory, plans projection, member roll-up and derived membership."""
import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.makerspaces.models import Makerspace, MakerspaceMembership
from apps.organizations.derived_membership import is_org_member, org_member_breakdown, org_member_count
from apps.organizations.models import Organization, OrganizationMakerspace, OrganizationMembership
from apps.organizations.org_member_rollup import member_rollup
from apps.organizations.public_directory import directory_organizations
from apps.accounts import rbac

pytestmark = pytest.mark.django_db


def org(slug="guild", **extra):
    values = dict(name=slug.title(), slug=slug, public_profile_enabled=True, is_discoverable=True)
    values.update(extra)
    return Organization.objects.create(**values)


def space(slug, organization=None, relationship="owner"):
    row = Makerspace.objects.create(name=slug.title(), slug=slug, public_site_enabled=True)
    if organization:
        OrganizationMakerspace.objects.create(organization=organization, makerspace=row, relationship=relationship)
    return row


def person(name):
    return User.objects.create_user(username=name, email=f"{name}@example.test")


def member(user, makerspace, status="active"):
    return MakerspaceMembership.objects.create(user=user, makerspace=makerspace, role="member", status=status)


def test_directory_needs_every_gate(settings):
    settings.ORGANIZATION_PUBLIC_DIRECTORY_ENABLED = True
    org("ok")
    org("not-discoverable", is_discoverable=False)
    org("no-profile", public_profile_enabled=False)
    org("pending", review_status="pending_review")
    org("inactive", is_active=False)
    assert [o.slug for o in directory_organizations()] == ["ok"]
    settings.ORGANIZATION_PUBLIC_DIRECTORY_ENABLED = False
    assert not directory_organizations().exists()
    assert APIClient().get(reverse("public-organization-directory")).status_code == 404


def test_directory_route_searches_by_name(settings):
    settings.ORGANIZATION_PUBLIC_DIRECTORY_ENABLED = True
    org("alpha")
    org("beta")
    data = APIClient().get(reverse("public-organization-directory"), {"search": "alp"}).json()
    assert [r["slug"] for r in data["results"]] == ["alpha"]
    assert "contact_email" not in data["results"][0]


def test_plans_projection_hides_when_module_off():
    owner = org()
    home = space("home", owner)
    from apps.organizations.public_plans import home_space_plans
    assert home_space_plans(owner) is None  # membership.public_plans is off
    assert home.pk


def test_rollup_counts_only_and_never_lists_people():
    owner = org()
    home = space("home", owner)
    other = space("other", owner, "manager")
    a, b = person("a"), person("b")
    member(a, home)
    member(b, home, "revoked")
    member(person("c"), other)  # manager-linked space does not count
    OrganizationMembership.objects.create(organization=owner, user=a)  # also explicit: counted once
    roll = member_rollup(owner)
    assert roll["people"]["total"] == 1 and roll["people"]["explicit"] == 1
    assert [(s["slug"], s["active"], s["revoked"]) for s in roll["spaces"]] == [("home", 1, 1)]
    flat = repr(roll)
    assert "a@example.test" not in flat and "username" not in flat


def test_derived_membership_rules():
    owner = org()
    home = space("home", owner)
    managed = space("managed", owner, "manager")
    affiliate = space("affil", owner, "affiliate")
    live, ended, mgr, aff = person("live"), person("ended"), person("mgr"), person("aff")
    member(live, home)
    row = member(ended, home)
    member(mgr, managed)
    member(aff, affiliate)
    assert is_org_member(live, owner) and is_org_member(ended, owner)
    assert not is_org_member(mgr, owner) and not is_org_member(aff, owner)
    MakerspaceMembership.objects.filter(pk=row.pk).update(status="revoked")  # revoke ends it live
    assert not is_org_member(ended, owner)
    User.objects.filter(pk=live.pk).update(access_status="restricted")
    assert not is_org_member(live, owner)
    assert org_member_count(owner) == 0


def test_derived_membership_confers_no_authority():
    owner = org()
    home = space("home", owner)
    user = person("derived")
    member(user, home)
    assert is_org_member(user, owner)
    assert not OrganizationMembership.objects.filter(organization=owner, user=user).exists()
    assert rbac.effective_actions(user, home.pk) == set()
    from apps.organizations import governance
    assert governance.actions_for(user, owner) == set()
    assert org_member_breakdown(owner)["derived_only"] == 1


def test_rollup_route_needs_governance_and_hides_other_orgs():
    owner = org()
    outsider = person("outsider")
    client = APIClient()
    client.force_authenticate(outsider)
    assert client.get(reverse("admin-organization-member-rollup", kwargs={"pk": owner.pk})).status_code in (403, 404)

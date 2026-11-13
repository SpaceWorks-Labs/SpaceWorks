"""Decision 295: /o/<slug> serves the workspace; own and partner rooms; wording."""
from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIClient

from apps.bookings.models import BookableSpace
from apps.bookings.organization_booking import _validated
from apps.makerspaces.models import Makerspace, MakerspaceMembership
from apps.makerspaces.public_page_access import canonical_url
from apps.makerspaces.space_kind import apply_kind_defaults
from apps.organizations.models import OrganizationMakerspace
from tests.makerspaces.space_pack_helpers import person
from tests.makerspaces.test_membership_j1 import member_role, user
from tests.parity_0120.o_b6.helpers import workspace

pytestmark = pytest.mark.django_db


def public_get(slug):
    return APIClient(HTTP_HOST="testserver").get(f"/api/v1/public/organizations/{slug}/")


def test_org_page_carries_the_workspace_events_rooms_and_plans():
    from apps.events.models import Event
    space, org = workspace("club")
    apply_kind_defaults(person("ob6-root", superadmin=True), space)
    now = timezone.now()
    Event.objects.create(makerspace=space, title="Open night", starts_at=now + timedelta(days=2),
                         ends_at=now + timedelta(days=2, hours=2), status="published", is_public=True,
                         location="Town hall")
    BookableSpace.objects.create(makerspace=space, name="Meeting room", kind="meeting", is_public=True, is_active=True)
    response = public_get(org.slug)
    assert response.status_code == 200, response.data
    data = response.data["workspace"]
    assert data["kind"] == "organization" and data["space_noun"] == "organization"
    assert [e["title"] for e in data["events"]] == ["Open night"]
    assert data["events"][0]["location"] == "Town hall"
    assert [r["name"] for r in data["rooms"]] == ["Meeting room"]


def test_org_page_has_no_workspace_block_for_a_makerspace_home_space():
    _, org = workspace("plainhome", kind="makerspace")
    assert public_get(org.slug).data["workspace"] is None


def test_slash_m_address_of_a_workspace_resolves_to_the_organization_page():
    space, org = workspace("redir")
    assert canonical_url("makerspace", space).endswith(f"/o/{org.slug}")
    plain, _ = workspace("redir2", kind="makerspace")
    assert canonical_url("makerspace", plain).endswith(f"/m/{plain.slug}")


def test_own_rooms_work_on_an_organization_workspace():
    space, _ = workspace("rooms")
    apply_kind_defaults(person("ob6-rooms-root", superadmin=True), space)
    room = BookableSpace.objects.create(makerspace=space, name="Hall", kind="other", is_public=True, is_active=True)
    from apps.bookings.website_visibility import public_spaces
    assert list(public_spaces(space)) == [room]


def test_an_organization_workspace_member_can_be_the_contact_for_a_partner_room():
    home, org = workspace("homeorg")
    partner = Makerspace.objects.create(name="Partner", slug="partner")
    OrganizationMakerspace.objects.create(organization=org, makerspace=partner, relationship="affiliate")
    contact = user("ob6-contact")
    for target in (home, partner):
        MakerspaceMembership.objects.create(
            makerspace=target, user=contact, assigned_role=member_role(target), role="custom",
            status="active", activated_at=timezone.now() - timedelta(days=30))
    room = BookableSpace.objects.create(makerspace=partner, name="Lab room", kind="meeting")
    _validated(room, org, contact)  # no OrganizationMembership row: the owned space's membership counts (293)


def test_an_outsider_is_still_refused_as_contact():
    home, org = workspace("homeorg2")
    partner = Makerspace.objects.create(name="Partner2", slug="partner2")
    OrganizationMakerspace.objects.create(organization=org, makerspace=partner, relationship="affiliate")
    stranger = user("ob6-stranger")
    room = BookableSpace.objects.create(makerspace=partner, name="Room", kind="meeting")
    with pytest.raises(ValidationError):
        _validated(room, org, stranger)

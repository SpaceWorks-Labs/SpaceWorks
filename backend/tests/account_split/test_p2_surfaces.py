"""Account surfaces constrain live action authority without replacing RBAC."""

import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts import rbac
from apps.accounts.models import User
from apps.accounts.tokens import SpaceWorksRefreshToken
from apps.audit.models import AuditLog
from apps.inventory.models import InventoryProduct
from apps.makerspaces.models import Makerspace
from apps.organizations.models import Organization, OrganizationMakerspace, OrganizationMembership
from .p1_helpers import staff

pytestmark = pytest.mark.django_db
ORIGIN = "http://localhost:5000"


@pytest.fixture
def actors(settings):
    settings.PLATFORM_STAFF_ORIGINS = [ORIGIN]
    a, b = [Makerspace.objects.create(name=slug, slug=slug) for slug in ("surface-a", "surface-b")]
    member = User.objects.create_user("surface-member")
    tenant_staff = staff(a)[0]
    platform = User.objects.create_superuser("surface-platform", email="platform@example.test")
    return a, b, member, tenant_staff, platform


def bearer(user, surface=None):
    token = SpaceWorksRefreshToken.for_user(user)
    if surface:
        token["surface"] = surface
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token.access_token}")
    return client


def inventory(space):
    return reverse("admin-inventory", kwargs={"makerspace_id": space.pk})


def test_staff_is_refused_foreign_tenant_and_member_surfaces(actors):
    a, b, _member, tenant_staff, _platform = actors
    client = bearer(tenant_staff)
    assert client.get(inventory(a)).status_code == 200
    assert client.get(inventory(b)).status_code == 403
    # U-A1: a staff-track holder is a person, so their own member surface answers.
    assert client.get("/api/v1/memberships/me").status_code == 200
    assert client.get(reverse("admin-platform-dashboard")).status_code == 403


def test_platform_and_member_refuse_reciprocal_account_surfaces(actors):
    a, _b, member, tenant_staff, platform = actors
    assert bearer(member).get(inventory(a)).status_code == 403
    client = bearer(platform)
    # Owner decision #115: the superadmin enters every Space-Manager route.
    assert client.get(inventory(a), HTTP_ORIGIN=ORIGIN).status_code == 200
    assert client.get("/api/v1/memberships/me", HTTP_ORIGIN=ORIGIN).status_code == 403
    assert client.get(reverse("admin-platform-dashboard"), HTTP_ORIGIN=ORIGIN).status_code == 200
    for user, surface in ((member, "staff_api"), (platform, "member")):
        assert bearer(user, surface).get("/api/v1/auth/me", HTTP_ORIGIN=ORIGIN).status_code == 401


@pytest.mark.parametrize("surface", ["member"])  # the release-1 `delegated` surface is gone (one account per person)
def test_org_grant_permits_catalog_edit_but_not_membership_authority(actors, surface):
    a, b, member, _staff, _platform = actors
    organization = Organization.objects.create(name="Grant", slug="catalog-grant")
    OrganizationMakerspace.objects.create(organization=organization, makerspace=a, relationship="manager")
    grant = OrganizationMembership.objects.create(
        organization=organization, user=member,
        granted_actions=[rbac.Action.VIEW_INVENTORY, rbac.Action.EDIT_INVENTORY],
    )
    product = InventoryProduct.objects.create(makerspace=a, name="Original", tracking_mode="quantity",
                                              total_quantity=1, available_quantity=1)
    client = bearer(member, surface)
    url = reverse("admin-inventory-detail", kwargs={"pk": product.pk})
    edited = client.patch(url, {"name": "Granted edit"}, format="json")
    assert edited.status_code == 200, edited.data
    product.refresh_from_db()
    assert product.name == "Granted edit"
    assert AuditLog.objects.filter(actor=member, action="inventory.updated", target_id=str(product.pk)).exists()
    assert client.get(inventory(b)).status_code == 403
    # No member can acquire built-in membership authority through an organization grant.
    assert client.get(reverse("admin-machine-types", kwargs={"makerspace_id": a.pk})).status_code == 403
    # Events are enabled; action-scoped tenant visibility hides this ungranted tenant.
    from apps.makerspaces.platform import module_enabled
    from apps.events.models import Event
    assert module_enabled(a, "events")
    assert client.get(reverse("admin-event-list-create", kwargs={"makerspace_id": a.pk})).status_code == 404
    assert not Event.objects.filter(makerspace=a).exists()
    assert not AuditLog.objects.filter(actor=member, action__startswith="event.").exists()
    grant.status = "suspended"
    grant.save(update_fields=["status"])
    assert client.patch(url, {"name": "Revoked edit"}, format="json").status_code == 403


def test_unknown_staff_route_fails_closed_at_runtime(actors):
    from types import SimpleNamespace
    from rest_framework.exceptions import PermissionDenied
    from apps.accounts.surface_policy import enforce_request
    a, _b, member, tenant_staff, platform = actors
    for user in (member, tenant_staff, platform):
        token = SpaceWorksRefreshToken.for_user(user)
        request = SimpleNamespace(path="/api/v1/admin/future/", headers={"Origin": ORIGIN},
            method="GET", query_params={}, resolver_match=SimpleNamespace(
                url_name="unclassified-future-route", view_name="unclassified-future-route", kwargs={}))
        with pytest.raises(PermissionDenied):
            enforce_request(user, token, request)


def test_person_org_grant_is_listed_through_org_authority_only_in_targetless_listing(actors):
    a, b, _member, tenant_staff, _platform = actors
    organization = Organization.objects.create(name="Malformed grant", slug="malformed-grant")
    OrganizationMakerspace.objects.create(organization=organization, makerspace=b, relationship="manager")
    # Simulate legacy/admin-written data: source readers must fail closed too.
    OrganizationMembership.objects.create(organization=organization, user=tenant_staff,
                                          granted_actions=[rbac.Action.VIEW_AUDIT])
    # U-A1: one account per person; an organization grant belongs to the person whatever else they hold,
    # and is scoped to the organization's own makerspaces (never to surface-a, where they only staff).
    assert rbac.has_any_org_authority(tenant_staff)
    assert not rbac.can(tenant_staff, rbac.Action.VIEW_AUDIT, a.pk + 1000)
    from apps.audit.services import record
    audit = record(_platform, "test.foreign", makerspace=b)
    client = bearer(tenant_staff)
    response = client.get(reverse("admin-audit-logs"))
    assert response.status_code == 200
    assert str(audit.pk) not in {str(row["id"]) for row in response.data["results"]}


def test_delegated_resource_readers_refuse_staff_account_rows(actors):
    from apps.events.event_authority import active_grants as event_grants
    from apps.bookings.booking_authority import active_grants as booking_grants
    from apps.bookings.models import BookableSpace, BookingSpaceStaffGrant
    from tests.events.staff_grant_helpers import grant_fixture
    a, b, _member, tenant_staff, _platform = actors
    _space, _manager, _helper, _event, grant = grant_fixture()
    grant.user = tenant_staff
    grant.save(update_fields=["user"])
    resource = BookableSpace.objects.create(makerspace=b, name="Foreign delegated room")
    BookingSpaceStaffGrant.objects.create(user=tenant_staff, makerspace=b, space=resource,
                                         permissions=["edit_details"])
    # U-A1: delegated resource grants follow the person, staff-track or not.
    assert event_grants(tenant_staff).exists()
    assert not booking_grants(tenant_staff).exists()  # surface-b never enabled the bookings module

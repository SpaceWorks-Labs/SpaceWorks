"""Decision 223 (k), lane L3b: an organization books a space for a partner event."""
from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.audit.models import AuditLog
from apps.bookings.calendar_render import booking_calendar
from apps.bookings.models import BookingOrganizationLink
from apps.bookings.organization_booking import book_for_organization, organization_name_for, organization_names
from apps.makerspaces.guards import SurfaceOff
from apps.organizations.models import Organization, OrganizationMakerspace, OrganizationMembership
from tests.bookings.staff_grant_helpers import client_for, grant_fixture

pytestmark = pytest.mark.django_db(transaction=True)
FEATURE = "bookings.organization_bookings"


def _world(slug="org-booking", *, link=True, feature=True, contact_in_org=True):
    tenant, manager, _grantee, resource, _grant, member = grant_fixture("manage_reservations", slug)
    if feature:
        tenant.enabled_features = sorted(set(tenant.enabled_features) | {FEATURE})
        tenant.save(update_fields=["enabled_features"])
    resource.approval_mode = "instant"
    resource.save(update_fields=["approval_mode"])
    org = Organization.objects.create(name="Partner Org", slug=f"{slug}-org")
    if link:
        OrganizationMakerspace.objects.create(organization=org, makerspace=tenant, relationship="affiliate")
    if contact_in_org:
        OrganizationMembership.objects.create(organization=org, user=member, status="active")
    return tenant, manager, resource, member, org


def _window(days=3):
    start = timezone.now() + timedelta(days=days)
    return {"starts_at": start, "ends_at": start + timedelta(hours=2)}


def test_booking_is_made_for_the_contact_and_recorded_against_the_organization():
    tenant, manager, resource, member, org = _world()
    booking = book_for_organization(manager, resource, org, member, **_window())
    assert booking.member_id == member.pk and booking.is_house is False
    link = BookingOrganizationLink.objects.get(booking=booking)
    assert (link.organization_id, link.organization_name, link.billed_member_id) == (org.pk, "Partner Org", member.pk)
    assert organization_name_for(booking) == "Partner Org" and organization_names([booking.pk]) == {booking.pk: "Partner Org"}
    entry = AuditLog.objects.get(makerspace=tenant, action="booking.organization_linked")
    assert entry.meta == {"organization_id": org.pk}


def test_calendar_summary_names_the_organization():
    _tenant, manager, resource, member, org = _world("org-booking-ics")
    booking = book_for_organization(manager, resource, org, member, **_window())
    assert b"Partner Org" in booking_calendar([booking])


def test_the_switch_the_link_and_the_contact_are_all_required():
    _tenant, manager, resource, member, org = _world("org-booking-off", feature=False)
    with pytest.raises(SurfaceOff):
        book_for_organization(manager, resource, org, member, **_window())
    _tenant, manager, resource, member, org = _world("org-booking-unlinked", link=False)
    with pytest.raises(ValidationError):
        book_for_organization(manager, resource, org, member, **_window())
    _tenant, manager, resource, member, org = _world("org-booking-contact", contact_in_org=False)
    with pytest.raises(ValidationError):
        book_for_organization(manager, resource, org, member, **_window())


def test_route_lists_choices_and_creates_the_booking():
    tenant, manager, resource, member, org = _world("org-booking-http")
    client = client_for(manager)
    choices = client.get(f"/api/v1/admin/spaces/{resource.pk}/organization-bookings/choices/")
    assert choices.status_code == 200
    assert choices.data == [{"organization_id": org.pk, "name": "Partner Org", "contacts": [
        {"member_id": member.pk, "name": choices.data[0]["contacts"][0]["name"]}]}]
    window = _window()
    created = client.post(f"/api/v1/admin/spaces/{resource.pk}/organization-bookings/", {
        "organization_id": org.pk, "contact_member_id": member.pk,
        "starts_at": window["starts_at"].isoformat(), "ends_at": window["ends_at"].isoformat()}, format="json")
    assert created.status_code == 201, created.data
    assert created.data["organization_name"] == "Partner Org"
    assert BookingOrganizationLink.objects.filter(booking_id=created.data["id"]).exists()


def test_unlinked_and_nonexistent_organization_answer_identically():
    _tenant, manager, resource, member, _org = _world("org-booking-oracle")
    stranger = Organization.objects.create(name="Elsewhere", slug="org-booking-oracle-else")
    client = client_for(manager)
    window = _window()
    url = f"/api/v1/admin/spaces/{resource.pk}/organization-bookings/"

    def post(org_id):
        return client.post(url, {"organization_id": org_id, "contact_member_id": member.pk,
                                 "starts_at": window["starts_at"].isoformat(),
                                 "ends_at": window["ends_at"].isoformat()}, format="json")

    unlinked, missing = post(stranger.pk), post(stranger.pk + 9999)
    assert unlinked.status_code == missing.status_code == 400
    assert unlinked.data == missing.data

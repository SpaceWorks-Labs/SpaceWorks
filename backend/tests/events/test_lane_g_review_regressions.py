"""Lane G route boundaries, nullable roster identities and native participation scope."""

import pytest
from django.urls import resolve, reverse
from rest_framework.test import APIClient

from apps.apiclients.scope_registry import (
    LEGACY_SCOPE, SCOPE_REGISTRY, lookup, scope_allows, validate_registry,
)
from apps.events.models import EventRegistration
from apps.makerspaces.models import MakerspaceMembership
from apps.organizations.models import OrganizationMembership
from tests.accounts.test_device_auth import attested_login
from tests.events.collab_helpers import client_for, collaborate, make_member
from tests.events.organization_audience_helpers import audience_fixture, direct, local
from tests.events.ticketing_helpers import account, public_url, signup

pytestmark = pytest.mark.django_db


def test_only_protected_lane_g_route_is_in_api_client_registry(settings):
    settings.HMAC_PROTECTED_PATH_PREFIXES = ["/api/public/", "/api/v1/public/"]
    venue, _, _, event, _ = audience_fixture()
    calendar_path = reverse("member-event-registration-calendar", args=[venue.pk, 1])
    eligibility_path = public_url(event, "public-event-organization-eligibility")
    assert not any(calendar_path.startswith(prefix) for prefix in settings.HMAC_PROTECTED_PATH_PREFIXES)
    assert any(eligibility_path.startswith(prefix) for prefix in settings.HMAC_PROTECTED_PATH_PREFIXES)
    for method in ("GET", "HEAD"):
        assert (resolve(calendar_path).view_name, method) not in SCOPE_REGISTRY
        entry = lookup(resolve(eligibility_path).view_name, method)
        assert scope_allows(entry, ["public:read"])
        assert not scope_allows(entry, [LEGACY_SCOPE])
    assert validate_registry() == ([], [])


@pytest.mark.parametrize("null_source", ["contact_only", "deleted_account"])
def test_staff_picker_ignores_null_members_but_excludes_registered_accounts(null_source):
    _, orgs, _, event, manager = audience_fixture()
    available = direct(orgs[0], "available")
    registered = direct(orgs[0], "registered")
    cancelled = direct(orgs[1], "cancelled")
    outsider = account("outsider")
    assert signup(event, registered).status_code == 201
    EventRegistration.objects.create(
        event=event, member=cancelled, name="Cancelled", email=cancelled.email,
        phone=cancelled.phone, status=EventRegistration.Status.CANCELLED,
    )
    # Historical imports/contact-only rows and account deletion both leave NULL FKs.
    former = account("former") if null_source == "deleted_account" else None
    historical = EventRegistration.objects.create(
        event=event, member=former, name="Historical participant",
        email="historical@example.test", phone="12345678",
    )
    if former:
        former.delete()
    historical.refresh_from_db()
    assert historical.member_id is None

    response = client_for(manager).get(reverse("admin-event-eligible-members", args=[event.pk]))

    assert response.status_code == 200, response.data
    ids = [row["member_id"] for row in response.data]
    assert set(ids) == {available.pk, cancelled.pk}
    assert manager.pk not in ids  # Staff use a separate member account to participate.
    assert len(ids) == len(set(ids))
    assert registered.pk not in ids and outsider.pk not in ids


def test_native_partner_calendar_uses_participation_tenant_and_exact_owner(settings, monkeypatch):
    venue, orgs, sources, event, _ = audience_fixture()
    partner = sources[0]
    partner.enabled_modules += ["mobile"]
    partner.save(update_fields=["enabled_modules"])
    owner = local(partner, "native-calendar-owner")
    outsider = make_member(partner, "native-calendar-outsider")
    collaborate(event, partner)
    created = client_for(owner).post(
        reverse("member-collaborative-event-register", args=[partner.pk, event.pk]),
        {}, format="json",
    )
    assert created.status_code == 201, created.data
    registration = event.registrations.get(member=owner)
    assert registration.registered_via_makerspace_id == partner.pk
    assert registration.event.makerspace_id == venue.pk != partner.pk
    # Lose the live organization proof while preserving active partner membership.
    orgs[0].is_active = False
    orgs[0].save(update_fields=["is_active"])
    assert not OrganizationMembership.objects.filter(user=owner).exists()

    path = reverse("member-event-registration-calendar", args=[partner.pk, registration.pk])
    ticket_path = reverse("member-event-ticket", args=[partner.pk, registration.pk])
    for user, expected in ((owner, 200), (outsider, 404)):
        user.set_password("strong-device-password")
        user.save(update_fields=["password"])
        login, _ = attested_login(APIClient(), user, settings, monkeypatch)
        assert login.status_code == 200, login.data
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
        headers = {"HTTP_X_MAKERSPACE_ID": str(partner.pk)}
        assert client.get(ticket_path, **headers).status_code == expected
        response = client.get(path, **headers)
        assert response.status_code == expected, getattr(response, "data", None)
        if user == owner:
            assert response["Content-Type"].startswith("text/calendar")
            assert response["Cache-Control"] == "private, no-store"
            assert b"BEGIN:VEVENT" in response.content
            # A header selecting a different tenant still fails before ownership.
            assert client.get(path, HTTP_X_MAKERSPACE_ID=str(venue.pk)).status_code == 403
            MakerspaceMembership.objects.filter(user=owner, makerspace=partner).update(status="revoked")
            assert client.get(path, **headers).status_code == 403

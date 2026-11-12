"""Native staff header end to end (decision 353, MOB-STAFF): matching space passes the gate, any mismatch is 403.

The grant is fixed to one makerspace and every staff request carries `X-Makerspace-Id`. These cases only assert
the *makerspace gate* (what the origin scope says); the route's own authority checks run after it, unchanged.
"""
from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.apiclients.models import ApiClient
from apps.events.models import Event
from tests.accounts.account_factories import make_membership, make_staff
from tests.accounts.native_helpers_m1d import attested_login, attested_staff_login
from tests.return_helpers import make_space, make_user

pytestmark = pytest.mark.django_db
PASSWORD = "strong-device-password"
GATE_REFUSALS = ("could not be resolved", "does not match", "delegated authority", "cannot use delegated", "query parameter")


def bearer(access):
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
    return client


def make_event(space):
    start = timezone.now() + timedelta(hours=1)
    return Event.objects.create(makerspace=space, title="Native event", starts_at=start, ends_at=start + timedelta(hours=1))


def refused_by_gate(response):
    return response.status_code == 403 and any(text in str(response.data) for text in GATE_REFUSALS)


@pytest.fixture
def phone(settings, monkeypatch):
    own, other = make_space("mobstaff-own"), make_space("mobstaff-other")
    user = make_staff(own, username="mobstaff-manager", password=PASSWORD, email="mobstaff@example.test")
    login, _ = attested_staff_login(APIClient(), user, settings, monkeypatch)
    return bearer(login.data["access"]), own, other


def call(client, space, method, path, **kwargs):
    return getattr(client, method)(path, HTTP_X_MAKERSPACE_ID=str(space.pk), **kwargs)


PROGRAMME_PATHS = (
    "/api/v1/admin/events/{pk}/tracks/",
    "/api/v1/admin/events/{pk}/judging-rounds/",
    "/api/v1/admin/events/{pk}/gallery/",
    "/api/v1/admin/events/{pk}/teams/",
    "/api/v1/admin/events/{pk}/broadcast-templates/",
)


@pytest.mark.parametrize("template", PROGRAMME_PATHS)
def test_event_programme_route_checks_the_events_space_against_the_header(phone, template):
    client, own, other = phone
    mine, theirs = make_event(own), make_event(other)
    assert not refused_by_gate(call(client, own, "get", template.format(pk=mine.pk)))
    mismatch = call(client, own, "get", template.format(pk=theirs.pk))
    assert mismatch.status_code == 403 and "does not match" in str(mismatch.data)
    missing = call(client, own, "get", template.format(pk=987654))
    # An unknown event has no space to compare: refused by the gate (or by the missing delegated source).
    assert refused_by_gate(missing)


def test_event_image_and_insights_resolve_their_space(phone):
    client, own, other = phone
    mine, theirs = make_event(own), make_event(other)
    assert not refused_by_gate(call(client, own, "delete", f"/api/v1/admin/events/{mine.pk}/image"))
    assert "does not match" in str(call(client, own, "delete", f"/api/v1/admin/events/{theirs.pk}/image").data)
    assert "does not match" in str(call(client, own, "get", f"/api/v1/admin/events/insights/?makerspace={other.pk}").data)
    assert not refused_by_gate(call(client, own, "get", f"/api/v1/admin/events/insights/?makerspace={own.pk}"))
    # A query listing must name the selected space explicitly.
    assert refused_by_gate(call(client, own, "get", "/api/v1/admin/events/insights/"))


def test_api_client_by_id_matches_the_selected_space_and_a_global_client_is_refused(phone):
    client, own, other = phone
    owned = ApiClient.objects.create(label="own", client_id="ck_mobstaff_own", secret_encrypted=b"x", makerspace=own)
    foreign = ApiClient.objects.create(label="foreign", client_id="ck_mobstaff_other", secret_encrypted=b"x", makerspace=other)
    global_client = ApiClient.objects.create(label="global", client_id="ck_mobstaff_global", secret_encrypted=b"x")
    assert not refused_by_gate(call(client, own, "get", f"/api/v1/admin/api-clients/{owned.pk}"))
    assert "does not match" in str(call(client, own, "get", f"/api/v1/admin/api-clients/{foreign.pk}").data)
    assert "could not be resolved" in str(call(client, own, "get", f"/api/v1/admin/api-clients/{global_client.pk}").data)
    rotate = call(client, own, "post", f"/api/v1/admin/api-clients/{foreign.pk}/rotate-secret")
    assert rotate.status_code == 403 and "does not match" in str(rotate.data)


def test_telegram_test_alert_takes_its_space_from_the_body(phone):
    client, own, other = phone
    refused = call(client, own, "post", "/api/v1/integrations/telegram/test-alert", data={"makerspace_id": other.pk}, format="json")
    assert refused.status_code == 403 and "does not match" in str(refused.data)
    assert not refused_by_gate(call(client, own, "post", "/api/v1/integrations/telegram/test-alert",
                                    data={"makerspace_id": own.pk}, format="json"))


def test_space_neutral_routes_accept_the_header_and_bulk_rows_stay_authorised_one_by_one(phone):
    client, own, other = phone
    listing = call(client, own, "get", "/api/v1/admin/makerspaces")
    assert listing.status_code == 200
    rows = listing.data if isinstance(listing.data, list) else listing.data["results"]
    assert {row["id"] for row in rows} == {own.pk}  # the grant's one space, never the others
    assert not refused_by_gate(call(client, own, "get", "/api/v1/admin/events/host-options/"))
    for kind in ("requests/accept", "bookings/approve", "event-registrations/approve"):
        response = call(client, own, "post", f"/api/v1/admin/bulk/{kind}", data={"ids": [987654]}, format="json")
        assert not refused_by_gate(response)
        assert response.status_code != 200  # an id this grant cannot see decides nothing


@pytest.mark.parametrize("path", (
    "/api/v1/admin/organizations/",
    "/api/v1/admin/organizations/7/",
    "/api/v1/admin/organizations/7/memberships/",
    "/api/v1/admin/organizations/7/events/insights/",
    "/api/v1/admin/organized-events/attendance/",
    "/api/v1/admin/space-pack-profiles",
    "/api/v1/admin/machine-service-report",
    "/api/v1/admin/reports/catalog",
    "/api/v1/admin/users/7/restrict",
))
def test_web_only_staff_routes_are_refused_for_a_native_staff_grant(phone, path):
    client, own, _other = phone
    method = "post" if path.endswith("restrict") else "get"
    response = call(client, own, method, path)
    assert response.status_code == 403 and "could not be resolved" in str(response.data)


def test_native_member_grant_can_redeem_an_event_staff_invite_but_not_a_booking_one(settings, monkeypatch):
    space = make_space("mobstaff-redeem")
    user = make_user("mobstaff-redeemer", password=PASSWORD)
    make_membership(user, space)
    login, _ = attested_login(APIClient(), user, settings, monkeypatch)
    client = bearer(login.data["access"])
    event = client.post("/api/v1/admin/event-staff-invites/redeem/", data={"token": "not-a-real-token"}, format="json")
    assert "cannot use delegated" not in str(event.data)
    booking = client.post("/api/v1/admin/booking-staff-invites/redeem/", data={"token": "not-a-real-token"}, format="json")
    assert booking.status_code == 403 and "cannot use delegated" in str(booking.data)

"""Native staff header end to end (decision 353, MOB-STAFF): matching space passes the gate, any mismatch is 403.

The grant is fixed to one makerspace and every staff request carries `X-Makerspace-Id`. Matching routes
must reach their intended handler; mismatches must return the exact makerspace-gate refusal.
"""
from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.apiclients.models import ApiClient
from apps.audit.models import AuditLog
from apps.bookings.models import BookingSpaceStaffGrant
from apps.events import services_staff_grants
from apps.events.models import Event, EventStaffGrant
from apps.events.hackathons.admission_models import HackathonConfig
from tests.accounts.account_factories import make_membership, make_staff
from tests.accounts.native_helpers_m1d import attested_login, attested_staff_login
from tests.return_helpers import make_space, make_user

pytestmark = pytest.mark.django_db
PASSWORD = "strong-device-password"
MISMATCH = "Makerspace target does not match the selected makerspace."
CONTEXT_MISMATCH = "Account context does not match this makerspace."
UNRESOLVED = "Makerspace target could not be resolved."


def bearer(access):
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
    return client


def make_event(space):
    start = timezone.now() + timedelta(hours=1)
    event = Event.objects.create(makerspace=space, title="Native event", starts_at=start, ends_at=start + timedelta(hours=1))
    HackathonConfig.objects.create(event=event, enabled=True)
    return event


def assert_gate_refusal(response, detail):
    assert response.status_code == 403
    assert response.data["code"] == "permission_denied"
    assert response.data["detail"] == detail


@pytest.fixture
def phone(settings, monkeypatch):
    own, other = make_space("mobstaff-own"), make_space("mobstaff-other")
    for space in (own, other):
        space.enabled_modules = sorted(set(space.enabled_modules or []) | {"events", "email", "notifications", "telegram"})
        space.enabled_features = sorted(set(space.enabled_features or []) | {
            "events.hackathons", "events.broadcasts", "events.broadcast_templates", "events.space_insights",
        })
        space.save(update_fields=["enabled_modules", "enabled_features"])
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
    admitted = call(client, own, "get", template.format(pk=mine.pk))
    assert admitted.status_code == 200
    if template.endswith("gallery/"):
        assert admitted.data == {"id": None, "version": 0, "result_revision_id": None, "entries": []}
    elif template.endswith("broadcast-templates/"):
        assert [row["key"] for row in admitted.data] == [
            "welcome", "week_before", "day_before", "doors_open", "logistics", "schedule", "time_change",
            "waitlist", "reviewing", "thanks", "missed_you", "feedback", "next_steps",
        ]
    else:
        assert admitted.data == {"count": 0, "next": None, "previous": None, "results": []}
    mismatch = call(client, own, "get", template.format(pk=theirs.pk))
    # The account surface pins the staff grant before native header validation runs.
    assert_gate_refusal(mismatch, CONTEXT_MISMATCH)
    missing = call(client, own, "get", template.format(pk=987654))
    assert missing.status_code == 403
    assert missing.data["code"] == "permission_denied"
    assert missing.data["detail"] == "A staff role in this makerspace is required."


def test_event_image_and_insights_resolve_their_space(phone):
    client, own, other = phone
    mine, theirs = make_event(own), make_event(other)
    cleared = call(client, own, "delete", f"/api/v1/admin/events/{mine.pk}/image")
    assert cleared.status_code == 200
    assert cleared.data["id"] == mine.pk
    assert cleared.data["image_url"] is None
    mine.refresh_from_db()
    assert mine.image_key == ""
    assert_gate_refusal(call(client, own, "delete", f"/api/v1/admin/events/{theirs.pk}/image"), CONTEXT_MISMATCH)
    assert_gate_refusal(call(client, own, "get", f"/api/v1/admin/events/insights/?makerspace={other.pk}"), CONTEXT_MISMATCH)
    insights = call(client, own, "get", f"/api/v1/admin/events/insights/?makerspace={own.pk}")
    assert insights.status_code == 200
    assert insights.data == {"window_days": 180, "k": 10, "top_events": [],
                             "returning": {"suppressed": True, "attendees": None, "returning_percent": None}}
    # A query listing must name the selected space explicitly.
    assert_gate_refusal(call(client, own, "get", "/api/v1/admin/events/insights/"),
                        "This listing requires its makerspace query parameter to match the selection.")


def test_api_client_by_id_matches_the_selected_space_and_a_global_client_is_refused(phone):
    client, own, other = phone
    owned = ApiClient.objects.create(label="own", client_id="ck_mobstaff_own", secret_encrypted=b"x", makerspace=own)
    foreign = ApiClient.objects.create(label="foreign", client_id="ck_mobstaff_other", secret_encrypted=b"x", makerspace=other)
    global_client = ApiClient.objects.create(label="global", client_id="ck_mobstaff_global", secret_encrypted=b"x")
    detail = call(client, own, "get", f"/api/v1/admin/api-clients/{owned.pk}")
    assert detail.status_code == 200
    assert {key: detail.data[key] for key in ("id", "label", "client_id", "makerspace")} == {
        "id": owned.pk, "label": "own", "client_id": "ck_mobstaff_own", "makerspace": own.pk,
    }
    assert_gate_refusal(call(client, own, "get", f"/api/v1/admin/api-clients/{foreign.pk}"), MISMATCH)
    assert_gate_refusal(call(client, own, "get", f"/api/v1/admin/api-clients/{global_client.pk}"), UNRESOLVED)
    rotate = call(client, own, "post", f"/api/v1/admin/api-clients/{foreign.pk}/rotate-secret")
    assert_gate_refusal(rotate, MISMATCH)


def test_telegram_test_alert_takes_its_space_from_the_body(phone, monkeypatch):
    client, own, other = phone
    sends = []
    monkeypatch.setattr("apps.integrations.views.send_message", lambda space, message: sends.append((space.pk, message)) or True)
    refused = call(client, own, "post", "/api/v1/integrations/telegram/test-alert", data={"makerspace_id": other.pk}, format="json")
    assert_gate_refusal(refused, CONTEXT_MISMATCH)
    assert sends == []
    admitted = call(client, own, "post", "/api/v1/integrations/telegram/test-alert",
                    data={"makerspace_id": own.pk, "message": "Native header test"}, format="json")
    assert admitted.status_code == 200
    assert admitted.data == {"delivered": True}
    assert sends == [(own.pk, "Native header test")]


def test_space_neutral_routes_accept_the_header_and_bulk_rows_stay_authorised_one_by_one(phone):
    client, own, other = phone
    listing = call(client, own, "get", "/api/v1/admin/makerspaces")
    assert listing.status_code == 200
    rows = listing.data if isinstance(listing.data, list) else listing.data["results"]
    assert {row["id"] for row in rows} == {own.pk}  # the grant's one space, never the others
    hosts = call(client, own, "get", "/api/v1/admin/events/host-options/")
    assert hosts.status_code == 200
    assert hosts.data == [{"id": own.pk, "name": own.name, "slug": own.slug}]
    for kind in ("requests/accept", "bookings/approve", "event-registrations/approve"):
        response = call(client, own, "post", f"/api/v1/admin/bulk/{kind}", data={"ids": [987654]}, format="json")
        assert response.status_code == 409
        assert response.data == {"code": "bulk_failed", "detail": "Nothing was changed: one item could not be decided.",
                                 "failed_id": 987654, "cause": "not_found"}


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
    assert_gate_refusal(response, UNRESOLVED)


def test_native_member_grant_can_redeem_an_event_staff_invite_but_not_a_booking_one(settings, monkeypatch):
    space = make_space("mobstaff-redeem")
    space.enabled_modules = sorted(set(space.enabled_modules or []) | {"events"})
    space.save(update_fields=["enabled_modules"])
    manager = make_staff(space, username="mobstaff-inviter")
    event = make_event(space)
    invite, token = services_staff_grants.create_invite(event, actor=manager, permissions=["check_in"])
    user = make_user("mobstaff-redeemer", password=PASSWORD)
    make_membership(user, space)
    login, _ = attested_login(APIClient(), user, settings, monkeypatch)
    assert login.status_code == 200
    client = bearer(login.data["access"])
    verified = client.post("/api/v1/auth/reauth", data={"password": PASSWORD}, format="json")
    assert verified.status_code == 200
    assert verified.data == {"verified": True, "expires_in": 600}
    redeemed = client.post("/api/v1/admin/event-staff-invites/redeem/", data={"token": token}, format="json")
    assert redeemed.status_code == 200
    grant = EventStaffGrant.objects.get(makerspace=space)
    assert {key: redeemed.data[key] for key in ("id", "makerspace", "event", "series", "user", "permissions")} == {
        "id": grant.pk, "makerspace": space.pk, "event": event.pk, "series": None,
        "user": user.pk, "permissions": ["check_in"],
    }
    assert (grant.event_id, grant.series_id, grant.user_id, grant.granted_by_id, grant.permissions) == (
        event.pk, None, user.pk, manager.pk, ["check_in"],
    )
    invite.refresh_from_db()
    assert invite.redeemed_by_id == user.pk
    assert invite.redeemed_at is not None
    audit = AuditLog.objects.get(makerspace=space, action="event.staff_grant_invite_redeemed")
    assert (audit.actor_id, audit.target_type, audit.target_id, audit.meta) == (
        user.pk, invite._meta.label_lower, str(invite.pk), {"permissions": ["check_in"]},
    )
    created = AuditLog.objects.get(makerspace=space, action="event.staff_grant_created")
    assert (created.actor_id, created.target_type, created.target_id, created.meta) == (
        user.pk, grant._meta.label_lower, str(grant.pk), {"permissions": ["check_in"]},
    )
    booking = client.post("/api/v1/admin/booking-staff-invites/redeem/", data={"token": token}, format="json")
    assert_gate_refusal(booking, "Native member sessions cannot use delegated authority.")
    assert not BookingSpaceStaffGrant.objects.filter(makerspace=space).exists()
    assert not AuditLog.objects.filter(makerspace=space, action__in=[
        "booking.staff_grant_created", "booking.staff_grant_invite_redeemed",
    ]).exists()

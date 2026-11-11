import pytest

from rest_framework.test import APIClient

from apps.audit.models import AuditLog
from apps.makerspaces.models import Makerspace, MakerspaceMembership, MakerspaceRole
from apps.accounts.models import User
from apps.presence.models import PresenceSession
from tests.account_split.p1_helpers import staff as staff_account


def member_client(space):
    user = User.objects.create_user(username=f"member-{space.slug}", email=f"member-{space.slug}@example.test", password="password")
    role = MakerspaceRole.objects.get(makerspace=space, slug="member")
    MakerspaceMembership.objects.create(makerspace=space, user=user, assigned_role=role, role="custom", status="active")
    client = APIClient(); client.force_authenticate(user)
    return client


@pytest.mark.django_db(transaction=True)
def test_dormant_and_enabled_geofence_presence_behaviour():
    """v2 §D: self check-in is HARD-geofenced (was advisory). Coordinates are never stored."""
    dormant = Makerspace.objects.create(name="Dormant", slug="dormant")
    dormant_client = member_client(dormant)
    refused = dormant_client.post("/api/v1/public/dormant/presence-sessions", {"duration_minutes": 60}, format="json")
    assert refused.status_code == 400 and refused.data["code"] == "geofence_unconfigured"
    space = Makerspace.objects.create(
        name="Fenced", slug="fenced", geofence_enabled=True, geofence_latitude="0", geofence_longitude="0",
        geofence_radius_m=25, presence_preset_minutes=[60, 120, 180, 240],
    )
    space.enabled_features = sorted(set(space.enabled_features or []) | {"presence.geofence"})
    space.save(update_fields=["enabled_features"])
    client = member_client(space)
    url = "/api/v1/public/fenced/presence-sessions"
    for body, code in (
        ({"duration_minutes": 60}, "location_required"),
        ({"duration_minutes": 120, "latitude": 0, "longitude": 0, "accuracy": 51}, "location_inaccurate"),
        ({"duration_minutes": 180, "latitude": 0, "longitude": 0.0002698, "accuracy": 0}, "outside_geofence"),
    ):
        response = client.post(url, body, format="json")
        assert response.status_code == 400 and response.data["code"] == code
    assert not PresenceSession.objects.filter(makerspace=space).exists()
    in_range = client.post(url, {"duration_minutes": 240, "latitude": 0, "longitude": 0.0001, "accuracy": 5}, format="json")
    assert in_range.status_code == 201
    metadata = AuditLog.objects.filter(action="presence.started", makerspace=space).latest("id").meta
    assert "latitude" not in metadata and "longitude" not in metadata and "accuracy" not in metadata
    assert PresenceSession.objects.filter(makerspace=space).count() == 1


@pytest.mark.django_db(transaction=True)
def test_manager_geofence_config_is_scoped_and_bootstrap_hides_reference_coordinates():
    mine = Makerspace.objects.create(name="Mine", slug="mine")
    other = Makerspace.objects.create(name="Other", slug="other")
    manager, _ = staff_account(mine, "manager", role="space_manager",
                               email="manager@example.test", password="password")
    client = APIClient(); client.force_authenticate(manager)
    assert client.patch(f"/api/v1/admin/makerspaces/{mine.id}", {"geofence_enabled": True}, format="json").status_code == 400
    response = client.patch(f"/api/v1/admin/makerspaces/{mine.id}", {"geofence_enabled": True, "geofence_latitude": 12.9716, "geofence_longitude": 77.5946, "geofence_radius_m": 25}, format="json")
    assert response.status_code == 200
    # A coordinates-only move (same enabled/radius) still shifts the enforced boundary → must be audited.
    moved = client.patch(f"/api/v1/admin/makerspaces/{mine.id}", {"geofence_latitude": 12.9800}, format="json")
    assert moved.status_code == 200
    assert AuditLog.objects.filter(action="makerspace.geofence_updated", makerspace=mine).count() == 2
    assert client.patch(f"/api/v1/admin/makerspaces/{other.id}", {"geofence_enabled": False}, format="json").status_code == 404
    payload = APIClient().get("/api/v1/bootstrap?slug=mine").data["makerspace"]
    assert payload["geofence_enabled"] is True
    assert "geofence_latitude" not in payload and "geofence_longitude" not in payload
    # Dormant space: the flag is OMITTED entirely (self-host byte-for-byte-unchanged invariant).
    dormant_payload = APIClient().get("/api/v1/bootstrap?slug=other").data["makerspace"]
    assert "geofence_enabled" not in dormant_payload


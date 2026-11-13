"""BK-H wire-level signature, tenant, scope and projection contracts."""
import pytest
from django.test import RequestFactory
from rest_framework.test import APIClient
from rest_framework.exceptions import AuthenticationFailed

from apps.accounts.models import User
from apps.apiclients.read_contract import SignedServerReadPermission
from apps.apiclients.scope_registry_booking_reads import booking_read_routes
from apps.audit.models import AuditLog
from apps.bookings.models import BookableSpace, Booking
from apps.bookings.views_integration import IntegrationBookingListView
from tests.bookings.integration_read_helpers import PREFIX, principal, read_world, signed

pytestmark = pytest.mark.django_db


def paths(w):
    return ["resources/", f"resources/{w.resource.pk}/", "bookings/",
            f"bookings/{w.booking.pk}/", f"resources/{w.resource.pk}/bookings/"]


@pytest.mark.parametrize("method", ["GET", "HEAD"])
def test_all_routes_require_verified_hmac_even_with_rollout_off(read_world, method):
    w = read_world
    for suffix in paths(w):
        path = PREFIX + suffix
        assert getattr(APIClient(), method.lower())(path).status_code == 401
        assert signed(w.client, path, method=method, signature="invalid").status_code == 401
        response = signed(w.client, path, method=method)
        assert response.status_code == 200
        assert response["Cache-Control"] == "private, no-store"
        assert response["Referrer-Policy"] == "no-referrer"
        if method == "HEAD":
            assert response.content == b""


@pytest.mark.parametrize("scopes", [["legacy:v1"], ["public:*"], ["public:read"],
                                    ["events:read"], ["bookings:attendance:read"]])
def test_legacy_public_and_attendance_only_cannot_read_reservations(read_world, scopes):
    row = principal(read_world.tenant, scopes)
    assert signed(row, PREFIX + "bookings/").status_code == 401


@pytest.mark.parametrize("kind", ["browser", "global", "revoked"])
def test_invalid_principals_fail_closed(read_world, kind):
    w = read_world
    row = principal(None if kind == "global" else w.tenant,
                    client_type="browser" if kind == "browser" else "server",
                    is_active=kind != "revoked")
    for suffix in paths(w):
        assert signed(row, PREFIX + suffix).status_code == 401


def test_user_or_resource_authority_cannot_replace_signature(read_world):
    user = User.objects.create_superuser(username="bkh-super", is_superuser=True, role="superadmin")
    client = APIClient()
    client.force_authenticate(user)
    assert client.get(PREFIX + "bookings/").status_code == 401
    request = RequestFactory().get(PREFIX + "bookings/")
    request.api_client = read_world.client
    with pytest.raises(AuthenticationFailed):
        SignedServerReadPermission().has_permission(request, IntegrationBookingListView())


def test_foreign_missing_and_unknown_targets_are_denied(read_world):
    w = read_world
    for suffix in [f"resources/{w.other.pk}/", f"resources/{w.other.pk}/bookings/",
                   f"bookings/{w.foreign_booking.pk}/", "bookings/999999999/", "unknown/"]:
        assert signed(w.client, PREFIX + suffix).status_code == 401
    assert signed(w.client, PREFIX + "bookings/malformed/").status_code == 401


@pytest.mark.parametrize("gate", ["feature", "module", "archived", "inactive"])
def test_live_tenant_and_feature_revocation(read_world, gate):
    from django.utils import timezone
    w = read_world
    if gate == "feature":
        w.tenant.enabled_features = []
    elif gate == "module":
        w.tenant.enabled_modules = [key for key in w.tenant.enabled_modules if key != "bookings"]
    elif gate == "archived":
        w.tenant.archived_at = timezone.now()
    else:
        w.tenant.lifecycle_state = "migrated_out"
    w.tenant.save()
    for suffix in paths(w):
        assert signed(w.client, PREFIX + suffix).status_code in (401, 404)


def test_scope_separation_and_exact_field_allow_lists(read_world):
    w = read_world
    resources = principal(w.tenant, ["booking_resources:read"])
    reservations = principal(w.tenant, ["bookings:read"])
    response = signed(resources, PREFIX + "resources/")
    assert response.status_code == 200
    data = response.json()["results"]
    assert [row["id"] for row in data] == [w.resource.pk]
    assert set(data[0]) == {"id", "name", "kind", "description", "capacity", "location", "is_active", "is_public", "public_page"}
    assert data[0]["public_page"] is None
    assert signed(resources, PREFIX + "bookings/").status_code == 401
    assert signed(reservations, PREFIX + "resources/").status_code == 401
    response = signed(reservations, PREFIX + "bookings/")
    assert response.status_code == 200
    row = response.json()["results"][0]
    assert set(row) == {"id", "resource_id", "starts_at", "ends_at", "status", "display_name"}
    assert row["id"] == w.booking.pk and row["display_name"] == "Ada Δ"
    assert row["resource_id"] == w.resource.pk
    for secret in [w.booking.email, w.booking.phone, w.booking.note, "private-answer",
                   str(w.booking.checkin_token), str(w.booking.public_token)]:
        assert secret not in response.content.decode()
    log = AuditLog.objects.filter(makerspace=w.tenant, action="api_client.bookings_read").latest("pk")
    assert set(log.meta) == {"principal_fingerprint", "rows", "attendance"}
    assert log.meta["rows"] == 1 and log.meta["attendance"] is False
    assert w.client.client_id not in str(log.meta)


def test_arrival_projection_keeps_completed_arrival_and_clears_reversal(read_world):
    from django.utils import timezone
    w = read_world
    arrived = timezone.now()
    Booking.objects.filter(pk=w.booking.pk).update(status="completed", arrived_at=arrived)
    path = PREFIX + f"bookings/{w.booking.pk}/"
    assert signed(w.client, path).json()["arrived_at"] is not None
    Booking.objects.filter(pk=w.booking.pk).update(arrived_at=None)
    assert signed(w.client, path).json()["arrived_at"] is None
    w.client.scopes = ["bookings:read"]
    w.client.save(update_fields=["scopes"])
    assert "arrived_at" not in signed(w.client, path).json()


def test_resource_reservations_never_include_another_resource(read_world):
    w = read_world
    second = BookableSpace.objects.create(makerspace=w.tenant, name="Second")
    Booking.objects.create(space=second, name="Other", email="other@example.test", phone="123",
                           starts_at=w.booking.starts_at, ends_at=w.booking.ends_at)
    response = signed(w.client, PREFIX + f"resources/{w.resource.pk}/bookings/")
    assert [row["id"] for row in response.json()["results"]] == [w.booking.pk]


def test_registry_entries_are_explicit_get_and_head_only():
    entries = booking_read_routes()
    assert len(entries) == 10
    for (_, method), entry in entries.items():
        assert method in {"GET", "HEAD"}
        assert entry.server_only and entry.tenant_bound and not entry.legacy_v1

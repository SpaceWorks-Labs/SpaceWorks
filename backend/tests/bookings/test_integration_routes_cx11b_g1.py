"""Signed-only reads: no browser/native route exists (BK-H, decisions 520/526)."""
import pytest
from django.core.cache import cache
from django.urls import reverse

from apps.audit.models import AuditLog
from tests.bookings.integration_read_helpers import principal, signed
from tests.bookings.route_support_cx11b_g1 import Route, world
from tests.modules.test_switch_matrix_objects_rest_isolation import rolled_back
from tests.modules.test_switch_matrix_objects_rest_support import domain_rows, no_domain_writes, switch

pytestmark = [pytest.mark.django_db, pytest.mark.area_bookings]
ROUTES = (
    "integration-booking-resource-list", "integration-booking-resource-detail",
    "integration-booking-resource-reservations", "integration-booking-list", "integration-booking-detail",
)


def pair(response):
    data = response.json()
    return response.status_code, data.get("code")


def prepare(name, settings):
    settings.API_CLIENT_AUTH_REQUIRED = False
    settings.HMAC_PROTECTED_PATH_PREFIXES = []
    settings.APICLIENT_REQUIRE_NONCE = True
    w = world(Route(name), False)
    w.principal = principal(w.tenant)
    w.foreign_principal = principal(w.foreign_tenant)
    w.insufficient = principal(w.tenant, scopes=["public:read"])
    w.reservations = name in {"integration-booking-resource-reservations", "integration-booking-list", "integration-booking-detail"}
    kwargs = {} if name.endswith("-list") else {"pk": w.booking.pk if name == "integration-booking-detail" else w.room.pk}
    w.path = reverse(name, kwargs=kwargs)
    return w


def read(w):
    cache.clear()
    before = set(AuditLog.objects.values_list("pk", flat=True))
    response = signed(w.principal, w.path)
    assert pair(response) == (200, None), response.content
    data = response.json()
    rows = data["results"] if "results" in data else [data]
    assert len(rows) == 1
    row = rows[0]
    if w.reservations:
        assert (row["id"], row["resource_id"], row["display_name"], row["status"]) == (
            w.booking.pk, w.room.pk, "G1 booker", "confirmed")
        assert set(row) == {"id", "resource_id", "display_name", "status", "starts_at", "ends_at", "arrived_at"}
        assert row["arrived_at"] is None
    else:
        assert (row["id"], row["name"], row["is_public"]) == (w.room.pk, w.room.name, True)
        assert row["public_page"] is None
    assert w.booking.email not in response.content.decode()
    assert w.booking.note not in response.content.decode()
    delta = list(AuditLog.objects.exclude(pk__in=before).order_by("pk"))
    assert [x.action for x in delta] == (["api_client.bookings_read"] if w.reservations else [])
    if delta:
        assert delta[0].meta["rows"] == 1
        assert delta[0].meta["attendance"] is True


def no_standing(w):
    cache.clear()
    before = domain_rows()
    with no_domain_writes():
        # A valid signature with insufficient scopes keeps the authentication contract.
        response = signed(w.insufficient, w.path)
    assert pair(response) == (401, None)
    assert response.json() == {"detail": "Invalid client signature."}
    if not w.path.endswith(("/resources/", "/bookings/")) or "resources/" in w.path and w.path.endswith("/bookings/"):
        with no_domain_writes():
            response = signed(w.foreign_principal, w.path)
        # Decision 520: valid signed foreign objects must be concealed as not_found.
        assert pair(response) == (404, "not_found"), response.content
    assert domain_rows() == before


@pytest.mark.parametrize("name", ROUTES)
def test_signed_route_effect_standing_and_independent_switches(name, settings):
    w = prepare(name, settings)
    with rolled_back():
        read(w)
    no_standing(w)
    for key in ("bookings", "bookings.api_read"):
        before = domain_rows()
        original = switch(w.tenant, key)
        no_standing(w)
        with no_domain_writes():
            response = signed(w.principal, w.path)
        assert pair(response) == (404, "not_found"), response.content
        assert domain_rows() == before
        switch(w.tenant, key, original=original)
        assert domain_rows() == before
        no_standing(w)
        with rolled_back():
            read(w)
    read(w)
    retained = domain_rows()
    for key in ("bookings", "bookings.api_read"):
        original = switch(w.tenant, key)
        assert domain_rows() == retained
        switch(w.tenant, key, original=original)
        assert domain_rows() == retained


@pytest.mark.parametrize("name", ROUTES)
def test_bad_signature_stays_an_authentication_refusal(name, settings):
    w = prepare(name, settings)
    for key in (None, "bookings", "bookings.api_read"):
        original = switch(w.tenant, key) if key else None
        before = domain_rows()
        with no_domain_writes():
            response = signed(w.principal, w.path, signature="invalid-signature")
        assert pair(response) == (401, None)
        assert response.json() == {"detail": "Invalid client signature."}
        assert domain_rows() == before
        if key:
            switch(w.tenant, key, original=original)

"""G1 grant routes: browser/native, seeded effects, standing and independent gates."""
import pytest

from tests.bookings.grant_routes_cx11b_g1 import ROUTES, setup
from tests.bookings.route_support_cx11b_g1 import prove, world

pytestmark = [pytest.mark.django_db, pytest.mark.area_bookings]


@pytest.mark.parametrize("native", [False, True], ids=["browser", "native"])
@pytest.mark.parametrize("route", ROUTES, ids=lambda route: route.id)
def test_grant_route_effect_standing_switches_and_retention(route, native, monkeypatch):
    prepared = world(route, native)
    setup(prepared, monkeypatch)
    if native and route.name == "booking-staff-invite-redeem":
        # No admitted native redemption surface: do not invent a successful handler.
        prove_native_redemption_unavailable(prepared)
        return
    prove(prepared)


def prove_native_redemption_unavailable(w):
    from django.urls import reverse
    from tests.bookings.route_support_cx11b_g1 import response_pair
    from tests.modules.test_switch_matrix_objects_rest_support import domain_rows, no_domain_writes, switch
    url = reverse(w.route.name)
    for key in (None, *w.route.keys):
        original = switch(w.tenant, key) if key else None
        before = domain_rows()
        with no_domain_writes():
            response = w.client.post(url, w.body, format="json")
        assert response_pair(response) == (403, "permission_denied")
        assert domain_rows() == before
        if key:
            switch(w.tenant, key, original=original)
            with no_domain_writes():
                response = w.client.post(url, w.body, format="json")
            assert response_pair(response) == (403, "permission_denied")
            assert domain_rows() == before


def test_native_member_invitation_redemption_keeps_decision_173_refusal(monkeypatch):
    from django.urls import reverse
    from tests.bookings.route_support_cx11b_g1 import person_client, response_pair
    from tests.modules.test_switch_matrix_objects_rest_support import domain_rows, no_domain_writes, switch
    route = next(row for row in ROUTES if row.name == "booking-staff-invite-redeem")
    w = world(route, True)
    setup(w, monkeypatch)
    client = person_client(w.member, w.tenant, True)
    url = reverse(route.name)
    for key in (None, *route.keys):
        original = switch(w.tenant, key) if key else None
        before = domain_rows()
        with no_domain_writes():
            response = client.post(url, w.body, format="json")
        assert response_pair(response) == (403, "permission_denied")
        assert domain_rows() == before
        if key:
            switch(w.tenant, key, original=original)
            with no_domain_writes():
                response = client.post(url, w.body, format="json")
            assert response_pair(response) == (403, "permission_denied")
            assert domain_rows() == before


@pytest.mark.parametrize("native", [False, True], ids=["browser", "native"])
def test_accessible_space_discovery_hides_retained_resource_grant_independently(native, monkeypatch):
    from tests.accounts.account_factories import grant_staff_role
    from apps.bookings.models_staff_grants import BookingSpaceStaffGrant
    from tests.bookings.route_support_cx11b_g1 import Route, equals
    from tests.modules.switch_matrix_object_helpers import client_for
    route = Route("admin-accessible-booking-spaces", keys=("bookings", "bookings.staff_grants"), standing="discovery")
    w = world(route, native)
    setup(w, monkeypatch)
    # A Handover role supplies native staff admission but no booking management.
    grant_staff_role(w.member, w.tenant, role_slug="handover")
    BookingSpaceStaffGrant.objects.create(makerspace=w.tenant, space=w.room, user=w.member,
        permissions=["edit_details"], granted_by=w.actor)
    w.client = client_for(w.member, w.tenant, native)
    w.off["bookings.staff_grants"] = (200, None)
    w.policy_off = lambda key, r: equals(r.data["results"], [])
    prove(w)

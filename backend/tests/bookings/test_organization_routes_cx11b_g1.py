"""G1 organization routes: browser/native, seeded effects, standing and independent gates."""
import pytest

from tests.bookings.organization_routes_cx11b_g1 import ROUTES, setup
from tests.bookings.route_support_cx11b_g1 import prove, world

pytestmark = [pytest.mark.django_db, pytest.mark.area_bookings]


@pytest.mark.parametrize("native", [False, True], ids=["browser", "native"])
@pytest.mark.parametrize("route", ROUTES, ids=lambda route: route.id)
def test_organization_route_effect_standing_switches_and_retention(route, native, monkeypatch):
    prepared = world(route, native)
    setup(prepared, monkeypatch)
    prove(prepared)

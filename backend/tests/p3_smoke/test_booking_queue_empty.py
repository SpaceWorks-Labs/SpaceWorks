"""Browser smoke regressions: a Booking Manager of a makerspace with no spaces gets empty lists, not 403."""

import pytest
from rest_framework.test import APIClient

from tests.modules.family_helpers import family_space
from tests.account_split.p1_helpers import staff

pytestmark = pytest.mark.django_db


def _manager(space, name):
    user, _ = staff(space, name, "space_manager", access_status="active")
    client = APIClient()
    client.force_authenticate(user)
    return client


@pytest.mark.parametrize("path", ["bookings/?status=pending", "booking-issues/?status=open"])
def test_manager_of_a_space_less_makerspace_gets_an_empty_page(path):
    space = family_space("queue-empty", "bookings")
    response = _manager(space, "queue-empty-manager").get(f"/api/v1/admin/makerspaces/{space.pk}/{path}")
    assert response.status_code == 200, response.content
    assert response.data["count"] == 0


@pytest.mark.parametrize("path", ["bookings/?status=pending", "booking-issues/?status=open"])
def test_actor_without_booking_authority_is_still_refused(path):
    space = family_space("queue-refused", "bookings")
    other = family_space("queue-refused-other", "bookings")
    response = _manager(other, "queue-refused-manager").get(f"/api/v1/admin/makerspaces/{space.pk}/{path}")
    assert response.status_code in (403, 404)

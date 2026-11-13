"""An unknown event is a 404 on the organizer submission reads, never a 500."""
import pytest

from apps.makerspaces.models import Makerspace
from tests.account_split.p1_helpers import staff
from tests.accounts.superadmin_parity_helpers import bearer

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("suffix", ["", "5/"])
def test_missing_event_submissions_are_not_found(suffix):
    space = Makerspace.objects.create(name="Sub 404", slug="sub-404")
    manager = staff(space, username="sub-404-sm", role="space_manager")[0]
    response = bearer(manager).get(f"/api/v1/admin/events/999999/submissions/{suffix}")
    assert response.status_code == 404, response.content
    assert response.json()["code"] == "not_found"

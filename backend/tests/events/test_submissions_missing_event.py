"""An unknown event on the organizer submission reads never answers 500 and never reveals existence.

MOB-STAFF (decision 353) resolves an event route's makerspace before the view runs, so a missing
event is refused by the surface gate. The answer must be byte-identical to the one for an event in
another makerspace the actor holds nothing in, or the status code would leak which ids exist.
"""
import pytest

from apps.makerspaces.models import Makerspace
from tests.account_split.p1_helpers import staff
from tests.accounts.superadmin_parity_helpers import bearer
from tests.events.checkin_helpers import make_event

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("suffix", ["", "5/"])
def test_missing_event_submissions_do_not_leak_existence(suffix):
    space = Makerspace.objects.create(name="Sub 404", slug="sub-404")
    other = Makerspace.objects.create(name="Sub 404 other", slug="sub-404-other")
    foreign = make_event(other)
    manager = staff(space, username="sub-404-sm", role="space_manager")[0]
    client = bearer(manager)
    missing = client.get(f"/api/v1/admin/events/999999/submissions/{suffix}")
    existing = client.get(f"/api/v1/admin/events/{foreign.pk}/submissions/{suffix}")
    assert missing.status_code == existing.status_code == 403, (missing.content, existing.content)
    assert missing.json() == existing.json()
    assert missing.json()["code"] == "permission_denied"

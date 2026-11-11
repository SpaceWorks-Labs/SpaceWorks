"""Release 0.12.0 U2: organizer room choices for the event room step."""
import pytest
from django.urls import reverse

from apps.accounts.rbac import Action
from apps.bookings.models import BookableSpace
from tests.machines.certification_helpers import _manager, _member, _space
from tests.return_helpers import authenticated_client

pytestmark = pytest.mark.django_db


def test_organizer_without_booking_roles_lists_active_rooms_without_booker_identities():
    space = _space("rooms", modules=("bookings", "events"), certifications=False)
    BookableSpace.objects.create(makerspace=space, name="Studio", capacity=8, approval_mode="instant")
    BookableSpace.objects.create(makerspace=space, name="Hall", capacity=40, approval_mode="approve")
    BookableSpace.objects.create(makerspace=space, name="Retired", is_active=False)
    BookableSpace.objects.create(makerspace=space, name="Laser time", kind="machine")
    other = _space("rooms-other", modules=("bookings", "events"), certifications=False)
    BookableSpace.objects.create(makerspace=other, name="Elsewhere")
    organizer, _ = _manager(space, "rooms-org", actions=(Action.MANAGE_EVENTS,))
    url = reverse("admin-event-room-choices", kwargs={"makerspace_id": space.pk})
    response = authenticated_client(organizer).get(url)
    assert response.status_code == 200
    rows = response.json()["results"]
    assert [row["name"] for row in rows] == ["Hall", "Studio"]
    assert set(rows[0]) == {"id", "name", "capacity", "needs_approval", "status"}
    assert rows[0]["needs_approval"] is True and rows[0]["status"] == "approval_required"
    assert rows[1]["status"] == "available"


def test_plain_member_and_other_spaces_staff_are_refused():
    space = _space("rooms2", modules=("bookings", "events"), certifications=False)
    member, _ = _member(space, "rooms2-member")
    url = reverse("admin-event-room-choices", kwargs={"makerspace_id": space.pk})
    assert authenticated_client(member).get(url).status_code in (403, 404)
    other = _space("rooms3", modules=("bookings", "events"), certifications=False)
    stranger, _ = _manager(other, "rooms3-org", actions=(Action.MANAGE_EVENTS,))
    assert authenticated_client(stranger).get(url).status_code in (403, 404)

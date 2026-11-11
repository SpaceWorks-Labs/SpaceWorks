"""The inviter's own limit is exposed for prefill; limited co-organizers can read their tracks."""
import pytest
from django.utils import timezone

from apps.events.contributions.models_roles import EventGrantEntitlement
from apps.events.models import EventStaffGrant
from apps.events.staff_grant_limits import my_limit
from tests.events.staff_grant_helpers import grant_fixture

pytestmark = pytest.mark.django_db


def _limited_co_organizer(*, track_ids, valid_until=None):
    space, manager, user, event, grant = grant_fixture("manage_team")
    EventGrantEntitlement.objects.filter(grant=grant).update(track_ids=track_ids, valid_until=valid_until)
    return space, manager, user, event, grant


def test_full_manager_and_unlimited_co_organizer_have_no_limit():
    space, manager, user, event, grant = grant_fixture("manage_team")
    assert my_limit(manager, event) is None
    assert my_limit(user, event) is None


def test_limited_co_organizer_gets_their_tracks_and_window():
    until = timezone.now() + timezone.timedelta(days=3)
    _space, _manager, user, event, _grant = _limited_co_organizer(track_ids=[5, 9], valid_until=until)
    limit = my_limit(user, event)
    assert limit["track_ids"] == [5, 9] and limit["valid_until"] == until and limit["valid_from"] is None


def test_non_delegating_helper_has_no_limit():
    _space, _manager, user, event, _grant = grant_fixture("check_in")
    assert my_limit(user, event) is None


def test_tracks_endpoint_is_readable_by_a_limited_co_organizer_but_scoped_to_their_tracks():
    from rest_framework.test import APIClient
    from apps.events.judging.models_definitions import HackathonTrack
    space, _manager, user, event, _grant = _limited_co_organizer(track_ids=[])
    mine = HackathonTrack.objects.create(event=event, makerspace=space, name="Mine")
    other = HackathonTrack.objects.create(event=event, makerspace=space, name="Other")
    EventGrantEntitlement.objects.filter(grant=_grant).update(track_ids=[mine.pk])
    client = APIClient()
    client.force_authenticate(user)
    response = client.get(f"/api/v1/admin/events/{event.pk}/tracks/")
    assert response.status_code == 200
    assert [row["id"] for row in response.data["results"]] == [mine.pk]
    assert other.pk not in [row["id"] for row in response.data["results"]]
    # Read-only: the definition editor stays closed.
    assert client.post(f"/api/v1/admin/events/{event.pk}/tracks/", {}, format="json").status_code in (400, 403)

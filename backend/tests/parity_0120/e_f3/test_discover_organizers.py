"""E-F3 (A14): the Discover organiser picker lists only public organisers of currently discoverable events."""
from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.events.models import Event
from apps.events.organizer_models import EventOrganizer
from apps.organizations.models import Organization
from tests.events.ticketing_helpers import event_space, open_event

pytestmark = pytest.mark.django_db(transaction=True)
URL = "/api/v1/discover/events/organizers/"


def _space(slug, switch=True):
    space = event_space(slug)
    space.public_site_enabled = True
    if switch:
        space.enabled_features = [*space.enabled_features, "events.discovery_filters"]
    space.save(update_fields=["public_site_enabled", "enabled_features"])
    return space


def _org(slug, **fields):
    return Organization.objects.create(name=slug.replace("-", " ").title(), slug=slug, **{"public_profile_enabled": True, **fields})


def _organise(event, org):
    EventOrganizer.objects.create(event=event, organization=org)


def test_lists_public_organisers_of_discoverable_events_only():
    space = _space("disc-org-a")
    listed, unlisted, ended = open_event(space), open_event(space, listing="unlisted"), open_event(space)
    Event.objects.filter(pk=ended.pk).update(starts_at=timezone.now() - timedelta(days=3), ends_at=timezone.now() - timedelta(days=2))
    _organise(listed, _org("gear-club"))
    _organise(listed, _org("quiet-club", public_profile_enabled=False))
    _organise(unlisted, _org("secret-club"))
    _organise(ended, _org("old-club"))
    response = APIClient().get(URL)
    assert response.status_code == 200
    assert response.data["results"] == [{"slug": "gear-club", "name": "Gear Club"}]
    assert set(response.data["results"][0]) == {"slug", "name"}
    assert "public" in response["Cache-Control"] and "max-age" in response["Cache-Control"]


def test_space_with_the_switch_off_or_outside_the_directory_contributes_nothing():
    off = _space("disc-org-b", switch=False)
    _organise(open_event(off), _org("off-club"))
    hidden = _space("disc-org-c")
    hidden.hidden_from_central_directory = True
    hidden.save(update_fields=["hidden_from_central_directory"])
    _organise(open_event(hidden), _org("hidden-dir-club"))
    assert APIClient().get(URL).data["results"] == []


def test_each_organiser_appears_once_and_by_name():
    space = _space("disc-org-d")
    zeta, alpha = _org("zeta-guild"), _org("alpha-guild")
    for event in (open_event(space), open_event(space)):
        _organise(event, zeta)
        _organise(event, alpha)
    assert [row["slug"] for row in APIClient().get(URL).data["results"]] == ["alpha-guild", "zeta-guild"]

"""Decision 246: HTTP and service condition matrix for the join funnel (switch, auth, validation, isolation)."""
from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.events.models import EventRegistration
from apps.makerspaces import join_funnel
from tests.events.checkin_helpers import make_event, register
from tests.makerspaces.l4_helpers import features_off, features_on
from tests.makerspaces.test_guest_passes import _space
from tests.makerspaces.test_membership_j1 import user

pytestmark = pytest.mark.django_db(transaction=True)


def _world(slug, *, funnel=True, events=True):
    makerspace = _space(slug)
    modules = set(makerspace.enabled_modules or [])
    makerspace.enabled_modules = sorted(modules | {"events"} if events else modules - {"events"})
    makerspace.save(update_fields=["enabled_modules"])
    if funnel:
        features_on(makerspace, "join_funnel")
    return makerspace


def _attended(makerspace, person):
    event = make_event(makerspace, starts_at=timezone.now() - timedelta(hours=50),
                       ends_at=timezone.now() - timedelta(hours=48))
    return register(event, person, status=EventRegistration.Status.ATTENDED)


def _get(account, makerspace, **query):
    client = APIClient()
    if account is not None:
        client.force_authenticate(account)
    return client.get(f"/api/v1/member/makerspaces/{makerspace.pk}/join-prefill", query)


def test_anonymous_is_refused_and_the_owner_gets_the_prefill():
    makerspace = _world("jfc-auth")
    guest = user("jfc-auth-guest")
    registration = _attended(makerspace, guest)
    assert _get(None, makerspace, registration_id=registration.pk).status_code in (401, 403)
    ok = _get(guest, makerspace, registration_id=registration.pk)
    assert ok.status_code == 200 and ok.json()["email"] == guest.email


def test_route_is_404_while_the_funnel_switch_is_off():
    makerspace = _world("jfc-off")
    guest = user("jfc-off-guest")
    registration = _attended(makerspace, guest)
    features_off(makerspace, "join_funnel")
    assert _get(guest, makerspace, registration_id=registration.pk).status_code == 404


@pytest.mark.parametrize("query", [{}, {"registration_id": "abc"}, {"registration_id": "999999"}, {"guest_pass_id": "999999"}])
def test_missing_garbled_or_unknown_sources_answer_404_source_not_found(query):
    makerspace = _world("jfc-valid")
    response = _get(user("jfc-valid-guest"), makerspace, **query)
    assert response.status_code == 404


def test_someone_elses_registration_and_another_spaces_registration_are_not_found():
    mine, theirs = _world("jfc-iso-a"), _world("jfc-iso-b")
    owner, stranger = user("jfc-iso-owner"), user("jfc-iso-stranger")
    registration = _attended(theirs, owner)
    assert _get(stranger, theirs, registration_id=registration.pk).status_code == 404
    assert _get(owner, mine, registration_id=registration.pk).status_code == 404


def test_events_module_off_hides_event_sources_and_zeroes_the_funnel_counts():
    makerspace = _world("jfc-noevents", events=False)
    guest = user("jfc-noevents-guest")
    assert _get(guest, makerspace, registration_id=1).status_code == 404
    assert join_funnel.funnel_counts(makerspace) == {"attendees": 0, "guests": 0, "joined": 0}


def test_funnel_counts_are_per_space():
    mine, theirs = _world("jfc-cnt-a"), _world("jfc-cnt-b")
    _attended(theirs, user("jfc-cnt-person"))
    assert join_funnel.funnel_counts(mine)["attendees"] == 0
    assert join_funnel.funnel_counts(theirs)["attendees"] == 1

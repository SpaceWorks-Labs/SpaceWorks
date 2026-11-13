"""MOD-2: the member crew-withdraw route (volunteer leaves an event crew) with its conditions."""

import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from apps.audit.models import AuditLog
from apps.events.models import EventCrewMember, EventParticipationSettings, EventRegistration
from tests.events.collab_helpers import client_for, make_event, make_member, make_space, make_staff

pytestmark = pytest.mark.django_db


def _world(slug):
    space = make_space(slug)
    space.enabled_features = ["events.crew"]
    space.save(update_fields=["enabled_features"])
    event = make_event(space, is_public=True)
    EventParticipationSettings.objects.create(makerspace=space, event=event, crew_signup_open=True,
                                              crew_approval_required=False)
    return space, event


def _signup(event, member):
    url = reverse("events-programme-member-crew-signup", kwargs={"pk": event.pk})
    response = client_for(member).post(url, {"crew_role": "AV", "dietary": ""}, format="json")
    assert response.status_code == 201, response.content
    return response


def _withdraw(event, user):
    return client_for(user).post(reverse("events-programme-member-crew-withdraw", kwargs={"pk": event.pk}))


def test_withdraw_ends_the_crew_place_and_cancels_its_registration():
    space, event = _world("crew-wd-ok")
    member = make_member(space, "crew-wd-m")
    _signup(event, member)
    crew = EventCrewMember.objects.get(event=event, member=member)
    assert crew.registration_id
    response = _withdraw(event, member)
    assert response.status_code == 200, response.content
    crew.refresh_from_db()
    assert crew.state == "withdrawn"
    assert EventRegistration.objects.get(pk=crew.registration_id).status == "cancelled"


def test_withdraw_twice_is_a_404_and_does_not_add_audit_rows():
    space, event = _world("crew-wd-twice")
    member = make_member(space, "crew-wd-twice-m")
    _signup(event, member)
    assert _withdraw(event, member).status_code == 200
    before = AuditLog.objects.count()
    assert _withdraw(event, member).status_code == 404
    assert AuditLog.objects.count() == before


def test_a_member_with_no_crew_row_and_signed_out_cannot_withdraw():
    space, event = _world("crew-wd-none")
    outsider = make_member(space, "crew-wd-outsider")
    assert _withdraw(event, outsider).status_code == 404
    assert APIClient().post(reverse("events-programme-member-crew-withdraw", kwargs={"pk": event.pk})
                            ).status_code in (401, 403)


def test_withdrawing_never_touches_another_members_crew_row():
    space, event = _world("crew-wd-other")
    one, two = make_member(space, "crew-wd-one"), make_member(space, "crew-wd-two")
    _signup(event, one)
    _signup(event, two)
    assert _withdraw(event, one).status_code == 200
    assert EventCrewMember.objects.get(event=event, member=two).state != "withdrawn"
    assert EventCrewMember.objects.get(event=event, member=one).state == "withdrawn"


def test_withdraw_is_off_with_the_crew_capability_and_the_row_is_kept():
    space, event = _world("crew-wd-off")
    member = make_member(space, "crew-wd-off-m")
    _signup(event, member)
    space.enabled_features = []
    space.save(update_fields=["enabled_features"])
    assert _withdraw(event, member).status_code == 404
    assert EventCrewMember.objects.get(event=event, member=member).state != "withdrawn"


def test_withdraw_on_another_tenants_event_is_404():
    space, event = _world("crew-wd-tenant")
    other_space = make_space("crew-wd-tenant-other")
    stranger = make_member(other_space, "crew-wd-stranger")
    assert _withdraw(event, stranger).status_code == 404

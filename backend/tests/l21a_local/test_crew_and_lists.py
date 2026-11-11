"""L21a crew (free place outside capacity, never staff authority) and custom check-in lists."""
from uuid import uuid4

import pytest
from django.urls import reverse

from apps.events import checkin_lists, event_authority
from apps.events.capacity import confirmed_occupancy, spots_left
from apps.events.contributions import crew_reads, crew_workflow
from apps.events.hackathons.admission_errors import ProgrammeError
from apps.events.models import (
    EventAddon, EventCheckInEvent, EventCheckInListScan, EventCrewMember, EventOrder, EventOrderLine,
    EventParticipationSettings, EventRegistration,
)
from apps.payments.models import Payment
from tests.events.collab_helpers import client_for, make_event, make_member, make_space, make_staff
from tests.events.test_registration_cancel_api import register

pytestmark = pytest.mark.django_db


def world(slug, *features, capacity=1, amount=None):
    space = make_space(slug)
    space.enabled_features = ["charges.enabled", "charges.events", *features]
    space.save(update_fields=["enabled_features"])
    event = make_event(space, is_public=True)
    event.capacity = capacity
    if amount:
        event.payment_amount = amount
    event.save()
    return space, event, make_staff(space)


def test_crew_place_is_free_outside_capacity_and_grants_no_staff_authority():
    space, event, staff = world("crew-a", "events.crew", capacity=1, amount=10)
    EventParticipationSettings.objects.create(makerspace=space, event=event, crew_signup_open=True)
    participant, volunteer = make_member(space, "crew-p"), make_member(space, "crew-v")
    register(event, participant)
    assert spots_left(event) == 0
    crew = crew_workflow.signup(event, actor=volunteer, crew_role="Door", dietary="vegan, nut allergy")
    assert crew.state == "applied" and crew.registration_id is None
    crew = crew_workflow.decide(event, actor=staff, crew_id=crew.pk, approve=True, expected_version=crew.version)
    place = EventRegistration.objects.get(pk=crew.registration_id)
    assert place.is_crew and place.status == "registered"
    event.refresh_from_db()
    assert confirmed_occupancy(event) == 1 and spots_left(event) == 0
    assert not Payment.objects.filter(subject_id=place.pk, subject_type="event_registration").exists()
    for permission in (None, "check_in", "manage_registrations", "manage_volunteers", "review_applications"):
        assert not event_authority.can(volunteer, event, permission)
    assert crew_reads.crew_flags([place.pk]) == {place.pk: "Door"}
    summary = crew_reads.catering(event)
    assert summary["approved"] == 1 and {row["label"] for row in summary["needs"]} == {"vegan", "nut allergy"}
    assert "crew-v" not in str(summary)
    crew_workflow.end(event, actor=volunteer, crew_id=crew.pk, own=True)
    place.refresh_from_db()
    assert place.status == "cancelled" and EventCrewMember.objects.get(pk=crew.pk).state == "withdrawn"


def test_crew_signup_link_is_closed_by_default_and_the_capability_gates_it():
    space, event, staff = world("crew-b", "events.crew")
    member = make_member(space, "crew-m")
    url = reverse("events-programme-member-crew-signup", kwargs={"pk": event.pk})
    assert client_for(member).get(url).status_code == 404
    EventParticipationSettings.objects.create(makerspace=space, event=event, crew_signup_open=True,
                                              crew_approval_required=False)
    response = client_for(member).post(url, {"crew_role": "AV", "dietary": ""}, format="json")
    assert response.status_code == 201 and response.json()["crew"]["state"] == "approved"
    space.enabled_features = ["charges.enabled"]
    space.save(update_fields=["enabled_features"])
    assert client_for(member).get(url).status_code == 404
    roster = reverse("events-programme-admin-crew", kwargs={"pk": event.pk})
    assert client_for(staff).get(roster).status_code == 404


def test_public_crew_section_needs_the_switch_and_an_opt_in():
    space, event, staff = world("crew-c", "events.crew")
    member = make_member(space, "crew-pub")
    crew = crew_workflow.add(event, actor=staff, member=member, crew_role="Host")
    EventCrewMember.objects.filter(pk=crew.pk).update(show_publicly=True)
    assert crew_reads.public_crew(event) == []  # the section switch is off
    EventParticipationSettings.objects.create(makerspace=space, event=event, crew_public_section=True)
    assert crew_reads.public_crew(event) == []  # no public profile: never shown


def _lists_world(slug):
    space, event, staff = world(slug, "events.checkin_lists", capacity=0)
    member = make_member(space, f"{slug}-m")
    registration = register(event, member)
    return space, event, staff, member, registration


def test_after_entry_rule_and_lists_never_touch_entry_checkin():
    space, event, staff, member, registration = _lists_world("lists-a")
    swag = checkin_lists.create(event, actor=staff, data={"name": "Swag", "kind": "swag", "after_entry": True})
    with pytest.raises(ProgrammeError) as exc:
        checkin_lists.scan(event, actor=staff, list_id=swag.pk, registration_id=registration.pk, operation_id=uuid4())
    assert exc.value.detail["code"] == "entry_required"
    EventRegistration.objects.filter(pk=registration.pk).update(status="attended")
    checkins = EventCheckInEvent.objects.count()
    scan, (allowed, used, reason) = checkin_lists.scan(event, actor=staff, list_id=swag.pk,
                                                       registration_id=registration.pk, operation_id=uuid4())
    assert (allowed, used, reason) == (1, 1, None)
    registration.refresh_from_db()
    assert registration.status == "attended" and EventCheckInEvent.objects.count() == checkins
    with pytest.raises(ProgrammeError) as exc:
        checkin_lists.scan(event, actor=staff, list_id=swag.pk, registration_id=registration.pk, operation_id=uuid4())
    assert exc.value.detail["code"] == "already_collected"
    with pytest.raises(ValueError):
        scan.delete()


def test_addon_list_counts_by_quantity_bought_on_paid_orders_and_archive_is_read_only():
    space, event, staff, member, registration = _lists_world("lists-b")
    shirt = EventAddon.objects.create(makerspace=space, event=event, name="T-shirt", kind="merch", amount=10)
    lunch = checkin_lists.create(event, actor=staff, data={"name": "Shirts", "kind": "swag", "addon_id": shirt.pk})
    assert checkin_lists.eligibility(lunch, registration)[2] == "not_eligible"
    order = EventOrder.objects.create(makerspace=space, event=event, buyer=member, currency="INR", status="paid", total=20)
    EventOrderLine.objects.create(order=order, kind="addon", addon=shirt, label="T-shirt", quantity=2,
                                  unit_amount=10, line_total=20)
    for _ in range(2):
        checkin_lists.scan(event, actor=staff, list_id=lunch.pk, registration_id=registration.pk, operation_id=uuid4())
    assert EventCheckInListScan.objects.filter(checkin_list=lunch).count() == 2
    with pytest.raises(ProgrammeError):
        checkin_lists.scan(event, actor=staff, list_id=lunch.pk, registration_id=registration.pk, operation_id=uuid4())
    checkin_lists.update(event, actor=staff, list_id=lunch.pk, data={"archive": True})
    with pytest.raises(ProgrammeError) as exc:
        checkin_lists.update(event, actor=staff, list_id=lunch.pk, data={"name": "x"})
    assert exc.value.detail["code"] == "list_archived"


def test_checkin_list_routes_are_off_without_the_capability():
    space, event, staff = world("lists-c")
    url = reverse("events-programme-admin-checkin-lists", kwargs={"pk": event.pk})
    assert client_for(staff).get(url).status_code == 404
    space.enabled_features = ["events.checkin_lists"]
    space.save(update_fields=["enabled_features"])
    assert client_for(staff).get(url).status_code == 200

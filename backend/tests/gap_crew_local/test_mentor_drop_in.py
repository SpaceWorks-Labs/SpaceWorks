"""Mentor Desk on any event (#128 C-36, E2-f): drop-in help and office hours without teams.

Hackathon teams keep the team-only path; on an event without hackathon teams a confirmed
attendee asks or books on their own and mentors see only a first name.
"""
from datetime import timedelta
from uuid import uuid4

import pytest
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.events.contributions.errors import ProgrammeError
from apps.events.contributions.models_shifts import EventShift
from apps.events.hackathons.admission_models import HackathonConfig
from apps.events.mentoring import help_workflow, office_hours_workflow, policy, projections
from apps.events.mentoring.models import EventHelpRequest
from apps.events.mentoring.models_queue import OfficeHoursBooking
from apps.events.models import EventRegistration
from apps.makerspaces.capabilities import FEATURES
from tests.events.programme.mentoring.helpers import help_payload, setup_help

pytestmark = pytest.mark.django_db


def drop_in(**extra):
    return {"operation_id": uuid4(), "expected_version": 0, "type_key": "pcb",
            "summary": "My board will not flash", "zone": {"table": "A1"}, **extra}


def attendee(event, user, status="registered"):
    return EventRegistration.objects.create(event=event, member=user, name=user.username, status=status,
                                            email=f"{user.username}@example.org",
                                            registered_via_makerspace=event.makerspace,
                                            payment_via_makerspace=event.makerspace)


def test_capability_graph_mentoring_no_longer_needs_hackathons():
    assert FEATURES["events.mentoring"].requires_features == ()
    assert set(FEATURES["events.mentor_rounds"].requires_features) == {"events.mentoring", "events.hackathons"}
    assert FEATURES["events.mentoring"].default_enabled is False


def test_mentoring_alone_is_enough_for_the_help_queue(settings):
    space, event, users, mentors, roles, team, _ = setup_help(settings)
    space.enabled_features = [key for key in space.enabled_features
                              if key not in ("events.hackathons", "events.mentor_rounds")]
    space.save(update_fields=["enabled_features"])
    attendee(event, users[1])
    row = help_workflow.create(actor=users[1], event_id=event.pk, payload=drop_in()).row
    assert row.team_id is None and row.origin == "attendee" and row.raised_by_id == users[1].pk


def test_attendee_drops_in_mentor_claims_and_resolves(settings):
    _, event, users, mentors, roles, _, _ = setup_help(settings)
    attendee(event, users[1])
    row = help_workflow.create(actor=users[1], event_id=event.pk, payload=drop_in()).row
    assert AuditLog.objects.filter(action="event.programme.help.raise_drop_in", target_id=str(row.pk)).exists()
    data = projections.help_request(row, actor=users[1], event=event, member=True)
    assert data["team_id"] is None and data["origin"] == "attendee" and data["team_alias"].endswith("(drop-in)")
    assert users[1].email not in str(data)
    claimed = help_workflow.command(actor=mentors[0], event_id=event.pk, help_id=row.pk,
        payload={"operation_id": uuid4(), "expected_version": row.version}, action="claim").row
    assert claimed.claimed_by_id == roles[0].pk
    resolved = help_workflow.command(actor=mentors[0], event_id=event.pk, help_id=row.pk,
        payload={"operation_id": uuid4(), "expected_version": claimed.version, "resolution_note": "Reflashed"},
        action="resolve").row
    assert resolved.state == "resolved"


def test_only_the_asker_reads_or_cancels_a_drop_in(settings):
    _, event, users, _, _, _, _ = setup_help(settings)
    attendee(event, users[0])
    attendee(event, users[1])
    row = help_workflow.create(actor=users[1], event_id=event.pk, payload=drop_in()).row
    with pytest.raises(ProgrammeError) as error:
        help_workflow.command(actor=users[0], event_id=event.pk, help_id=row.pk,
            payload={"operation_id": uuid4(), "expected_version": row.version}, action="cancel", member_surface=True)
    assert error.value.status_code == 404
    cancelled = help_workflow.command(actor=users[1], event_id=event.pk, help_id=row.pk,
        payload={"operation_id": uuid4(), "expected_version": row.version}, action="cancel", member_surface=True).row
    assert cancelled.state == "cancelled"


@pytest.mark.parametrize("status", [None, "cancelled", "waitlisted"])
def test_drop_in_needs_a_confirmed_registration(settings, status):
    _, event, users, _, _, _, _ = setup_help(settings)
    if status:
        attendee(event, users[1], status=status)
    with pytest.raises(ProgrammeError) as error:
        help_workflow.create(actor=users[1], event_id=event.pk, payload=drop_in())
    assert error.value.detail["code"] == "registration_required"
    assert not EventHelpRequest.objects.filter(event=event).exists()


def test_a_team_hackathon_keeps_the_team_only_queue(settings):
    _, event, users, mentors, _, team, _ = setup_help(settings)
    HackathonConfig.objects.create(event=event, enabled=True)
    attendee(event, users[1])
    assert not policy.drop_in_allowed(event)
    with pytest.raises(ProgrammeError) as error:
        help_workflow.create(actor=users[1], event_id=event.pk, payload=drop_in())
    assert error.value.detail["code"] == "team_required"
    row = help_workflow.create(actor=users[0], event_id=event.pk, payload=help_payload(team.pk)).row
    assert row.team_id == team.pk and row.origin == "team"
    with pytest.raises(ProgrammeError) as error:  # a mentor still raises help for a team
        help_workflow.create(actor=mentors[0], event_id=event.pk, payload=drop_in(), mentor_origin=True)
    assert error.value.detail["code"] == "team_required"


def test_the_open_limit_counts_per_asker(settings):
    _, event, users, _, _, _, _ = setup_help(settings)
    attendee(event, users[0])
    attendee(event, users[1])
    help_workflow.create(actor=users[1], event_id=event.pk, payload=drop_in())
    with pytest.raises(ProgrammeError) as error:
        help_workflow.create(actor=users[1], event_id=event.pk, payload=drop_in())
    assert error.value.detail["code"] == "help_limit_reached"
    assert help_workflow.create(actor=users[0], event_id=event.pk, payload=drop_in()).row.raised_by_id == users[0].pk


def test_a_mentor_never_claims_their_own_drop_in(settings):
    _, event, _, mentors, roles, _, _ = setup_help(settings)
    attendee(event, mentors[0])
    row = help_workflow.create(actor=mentors[0], event_id=event.pk, payload=drop_in()).row
    _, profile = policy.mentor_for(mentors[0], event)
    assert not policy.request_eligible(assignment=roles[0], profile=profile, row=row)
    with pytest.raises(ProgrammeError) as error:
        help_workflow.command(actor=mentors[0], event_id=event.pk, help_id=row.pk,
            payload={"operation_id": uuid4(), "expected_version": row.version}, action="claim")
    assert error.value.detail["code"] == "mentor_not_eligible"


def _office_slot(event, role):
    from apps.events.contributions.models import EventRolePosting
    posting = EventRolePosting.objects.create(event=event, makerspace=event.makerspace, role="mentor",
        title="Office hours", opens_at=event.starts_at, closes_at=event.ends_at)
    return EventShift.objects.create(event=event, makerspace=event.makerspace, posting=posting, kind="office_hours",
        mentor_assignment=role, starts_at=timezone.now() + timedelta(minutes=30),
        ends_at=timezone.now() + timedelta(minutes=50), signup_deadline=timezone.now() + timedelta(minutes=20),
        task="Electronics clinic", capacity=2)


@pytest.mark.django_db(transaction=True)
def test_drop_in_office_hours_book_and_cancel(settings):
    _, event, users, _, roles, _, _ = setup_help(settings)
    attendee(event, users[1])
    slot = _office_slot(event, roles[0])
    booking = office_hours_workflow.book(actor=users[1], event_id=event.pk, slot_id=slot.pk,
        payload={"operation_id": uuid4(), "expected_version": slot.version}).row
    assert booking.team_id is None and booking.booked_by_id == users[1].pk
    with pytest.raises(ProgrammeError) as error:  # one live drop-in booking per person and slot
        office_hours_workflow.book(actor=users[1], event_id=event.pk, slot_id=slot.pk,
            payload={"operation_id": uuid4(), "expected_version": EventShift.objects.get(pk=slot.pk).version})
    assert error.value.detail["code"] == "booking_conflict"
    with pytest.raises(ProgrammeError):
        office_hours_workflow.cancel(actor=users[0], event_id=event.pk, booking_id=booking.pk,
            payload={"operation_id": uuid4(), "expected_version": booking.version})
    cancelled = office_hours_workflow.cancel(actor=users[1], event_id=event.pk, booking_id=booking.pk,
        payload={"operation_id": uuid4(), "expected_version": booking.version}).row
    assert cancelled.state == "cancelled"
    assert OfficeHoursBooking.objects.filter(pk=booking.pk, state="cancelled").exists()


def test_drop_in_routes_over_http(settings):
    from django.urls import reverse
    from tests.events.collab_helpers import client_for
    space, event, users, _, _, _, _ = setup_help(settings)
    attendee(event, users[1])
    url = reverse("events-programme-member-help-collection", kwargs={"makerspace_id": space.pk, "pk": event.pk})
    body = drop_in()
    # The programme API requires Idempotency-Key to equal operation_id.
    response = client_for(users[1]).post(url, body, format="json", HTTP_IDEMPOTENCY_KEY=str(body["operation_id"]))
    assert response.status_code == 201, response.content
    assert response.json()["origin"] == "attendee"
    listed = client_for(users[1]).get(url).json()["results"]
    assert [row["id"] for row in listed] == [response.json()["id"]]
    assert client_for(users[0]).get(url).json()["results"] == []  # another member sees nothing of it
    slots = reverse("events-programme-member-office-hours-list", kwargs={"makerspace_id": space.pk, "pk": event.pk})
    assert client_for(users[1]).get(slots).status_code == 200
    # users[0] leads the setup team, so the team path admits them; the drop-in refusal is for a
    # person with neither a registration nor a team.
    from tests.events.ticketing_helpers import account
    assert client_for(users[0]).get(slots).status_code == 200
    assert client_for(account(f"outsider-{uuid4().hex[:10]}")).get(slots).status_code == 403


def test_switch_off_refuses_drop_ins(settings):
    space, event, users, _, _, _, _ = setup_help(settings)
    attendee(event, users[1])
    space.enabled_features = [key for key in space.enabled_features if key != "events.mentoring"]
    space.save(update_fields=["enabled_features"])
    with pytest.raises(Exception) as error:
        help_workflow.create(actor=users[1], event_id=event.pk, payload=drop_in())
    assert getattr(error.value, "status_code", None) in (403, 404)
    assert not EventHelpRequest.objects.filter(event=event).exists()

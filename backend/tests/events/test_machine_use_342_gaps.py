"""Decision 342 gaps closed: machine-time bookings carry the event link, no N+1 on lists, reports in the catalogue.

Not run in source preparation (TEST-3 owns the stack).
"""
from datetime import timedelta

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.audit.models import AuditLog
from apps.events import machine_use_services as services
from apps.events.models import Event, EventRegistration
from apps.events.models_machine_use import MachineEventLink
from apps.machines import event_use, sessions_service as service
from apps.operations.report_coverage import REPORT_MODULE_COVERAGE
from apps.operations.report_registry import REPORT_DEFINITIONS
from tests.events.test_event_workshop_machines import book, world as booking_world
from tests.machines.session_helpers import session_world

pytestmark = pytest.mark.django_db(transaction=True)


def tag_event(maker, member, title="Faire"):
    start = timezone.now() + timedelta(days=3)
    event = Event.objects.create(makerspace=maker, title=title, starts_at=start, ends_at=start + timedelta(hours=2),
                                 status=Event.Status.PUBLISHED)
    EventRegistration.objects.create(event=event, member=member, name=member.username, email=member.email,
                                     phone=member.phone or "1", status=EventRegistration.Status.REGISTERED)
    return event


def test_requester_tags_a_machine_time_booking_with_an_eligible_event():
    maker, staff, member, _event, _kinds, times = booking_world("mb-attach")
    booking = book(times[0], member, _event)
    mine = tag_event(maker, member)
    link = event_use.attach(booking, mine.pk, actor=member)
    assert (link.booking_id, link.session_id, link.service_request_id) == (booking.pk, None, None)
    meta = AuditLog.objects.get(action="machine_event.linked").meta
    assert meta["booking_id"] == booking.pk and meta["after_event_id"] == mine.pk


def test_booking_link_needs_eligibility_and_a_machine_space():
    maker, staff, member, event, _kinds, times = booking_world("mb-refuse")
    booking = book(times[0], member, event)
    with pytest.raises(ValidationError) as caught:
        event_use.attach(booking, event.pk, actor=member)  # a draft event the member is not part of
    assert caught.value.detail["code"] == "event_not_eligible"
    from apps.bookings.models import BookableSpace
    BookableSpace.objects.filter(pk=booking.space_id).update(kind=BookableSpace.Kind.MEETING)
    booking.refresh_from_db()
    booking.space.refresh_from_db()
    mine = tag_event(maker, member, "Other")
    with pytest.raises(ValidationError) as caught:
        event_use.attach(booking, mine.pk, actor=member)
    assert caught.value.detail["code"] == "not_machine_booking"
    assert not MachineEventLink.objects.exists()


def test_area_manager_sets_changes_and_clears_a_booking_link_with_before_and_after():
    maker, staff, member, event, _kinds, times = booking_world("mb-manage")
    booking = book(times[0], member, event)
    second = tag_event(maker, member, "Second")
    services.manage(staff, booking, event.pk)
    services.manage(staff, booking, second.pk)
    assert services.manage(staff, booking, None) is None
    changed = AuditLog.objects.get(action="machine_event.changed").meta
    assert (changed["before_event_id"], changed["after_event_id"], changed["booking_id"]) == (event.pk, second.pk, booking.pk)
    assert AuditLog.objects.filter(action="machine_event.cleared").count() == 1
    assert not MachineEventLink.objects.exists()


def test_list_queries_do_not_issue_one_query_per_event_link():
    w = session_world("mb-n1")
    w.space.enabled_modules = sorted(set(w.space.enabled_modules) | {"events", "machines"})
    w.space.save(update_fields=["enabled_modules"])
    from apps.machines.models import MachineSession
    for index in range(4):
        service.stop(service.start(w.machines[index % 2], w.member, actor=w.member, source="member_qr"),
                     actor=w.member, reason="member")
    rows = event_use.with_event(MachineSession.objects.filter(makerspace=w.space))
    assert "events_machineeventlink" in str(rows.query)
    with CaptureQueriesContext(connection) as queries:
        summaries = [event_use.event_summary(row) for row in rows]
    assert summaries == [None] * 4 and len(queries) == 1


def test_the_two_event_reports_are_registered_and_covered_by_the_machines_module():
    keys = {definition.key for definition in REPORT_DEFINITIONS}
    assert {"machine-use-by-event", "event-machine-use"} <= keys
    assert {"machine-use-by-event", "event-machine-use"} <= set(REPORT_MODULE_COVERAGE["machines"].reports)
    by_key = {definition.key: definition for definition in REPORT_DEFINITIONS}
    assert by_key["event-machine-use"].identity_bearing and by_key["event-machine-use"].subject_kind == "event"
    assert not by_key["machine-use-by-event"].deployment_aggregate and "bookings" in by_key["machine-use-by-event"].fields


def test_by_event_report_counts_a_booking_link_for_a_machine_manager_in_scope():
    from apps.operations.reports_machine_event import build_machine_use_by_event
    maker, staff, member, event, _kinds, times = booking_world("mb-report")
    booking = book(times[0], member, event)
    services.manage(staff, booking, event.pk)
    rows = build_machine_use_by_event(maker.pk, actor=staff).records
    assert [row["bookings"] for row in rows] == [1]


def test_staff_with_machine_authority_tags_a_new_booking_with_any_open_event_of_the_space():
    maker, staff, member, event, _kinds, times = booking_world("mb-staff")
    booking = book(times[0], member, event)  # stands in for the booking staff just created
    other = Event.objects.create(makerspace=maker, title="Not the member's", starts_at=timezone.now() + timedelta(days=5),
                                 ends_at=timezone.now() + timedelta(days=5, hours=1), status=Event.Status.PUBLISHED)
    link = event_use.staff_attach(staff, booking, other.pk)
    assert (link.event_id, link.source, link.booking_id) == (other.pk, "manager", booking.pk)


def test_staff_without_machine_authority_is_held_to_the_members_events():
    from tests.fixed_roles.helpers import staff_account
    maker, staff, member, event, _kinds, times = booking_world("mb-staff-plain")
    booking = book(times[0], member, event)
    plain = staff_account("plain-" + maker.slug, maker)  # a role with no machine authority
    with pytest.raises(ValidationError) as caught:
        event_use.staff_attach(plain, booking, event.pk)  # a draft event the member is not part of
    assert caught.value.detail["code"] == "event_not_eligible"
    assert event_use.staff_attach(plain, booking, None) is None


def test_booking_list_serializer_carries_the_event_without_a_query_per_row():
    from apps.bookings.models import Booking
    from apps.bookings.serializers_reservation import BookingAdminSerializer
    maker, staff, member, event, _kinds, times = booking_world("mb-list")
    booking = book(times[0], member, event)
    services.manage(staff, booking, event.pk)
    rows = list(event_use.with_event(Booking.objects.filter(pk=booking.pk).select_related("space__makerspace")))
    assert "event" in BookingAdminSerializer.Meta.fields
    with CaptureQueriesContext(connection) as queries:
        summary = event_use.event_summary(rows[0])
    assert summary == {"id": event.pk, "title": event.title} and len(queries) == 0


def test_recurring_booking_input_has_no_event_field_and_staff_create_input_has_one():
    from apps.bookings.serializers_staff_booking import StaffSingleBookingInputSerializer
    from apps.bookings.views_recurrence import RecurringBookingInputSerializer
    assert "event_id" in StaffSingleBookingInputSerializer().fields
    assert "event_id" not in RecurringBookingInputSerializer().fields


def test_staff_options_route_lists_open_events_only_for_machine_or_booking_staff():
    from django.urls import reverse
    from rest_framework.test import APIClient
    maker, staff, member, event, _kinds, times = booking_world("mb-options")
    Event.objects.create(makerspace=maker, title="Gone", starts_at=timezone.now() + timedelta(days=2),
                         ends_at=timezone.now() + timedelta(days=2, hours=1), status=Event.Status.CANCELLED)
    client = APIClient()
    client.force_authenticate(staff)
    url = reverse("admin-machine-use-event-options", kwargs={"makerspace_id": maker.pk})
    titles = [row["title"] for row in client.get(url).data]
    assert event.title in titles and "Gone" not in titles
    client.force_authenticate(member)
    assert client.get(url).status_code in (403, 404)

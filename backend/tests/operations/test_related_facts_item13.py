"""Decision 216 item 13: registration, attendance, arrival, presence and machine sessions
stay independent facts; the related-facts views show them side by side, read-only."""

from datetime import timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework.exceptions import APIException, NotFound, PermissionDenied
from rest_framework.test import APIClient

from apps.accounts.rbac import Action
from apps.bookings.models import BookableSpace, Booking, BookingCheckInEvent, BookingSpaceStaffGrant
from apps.bookings.services_bookings import create_booking
from apps.events.models import Event, EventCheckInEvent, EventRegistration
from apps.machines.models import Machine, MachineSession, MachineType
from apps.operations.related_facts import booking_facts, event_facts
from apps.presence.models import PresencePreference, PresenceSession, PresenceSettings
from tests.account_split_g2_helpers import staff_for_actions
from tests.events.manual_grant_fixture import create_manual_grant
from tests.machines.certification_helpers import _member, _space
from tests.return_helpers import make_member, make_user

pytestmark = pytest.mark.django_db
MODULES = ("machines", "bookings", "events", "presence")
FEATURES = {"machines.sessions", "bookings.confirmations", "bookings.checkin", "bookings.staff_grants"}  # checkin requires confirmations


def _features(space, add=(), remove=()):
    space.enabled_features = sorted((set(space.enabled_features or []) | set(add)) - set(remove))
    space.save(update_fields=["enabled_features"])


def _modules(space, remove=()):
    space.enabled_modules = sorted(set(space.enabled_modules) - set(remove))
    space.save(update_fields=["enabled_modules"])


def _presence(space, user, start, minutes=60, *, membership=None, hidden=False, registration=None):
    return PresenceSession.objects.create(
        account=user, member=user, makerspace=space, membership=membership, status="visiting",
        started_at=start, expires_at=start + timedelta(minutes=minutes), hide_on_display=hidden,
        event_registration=registration)


def _machine_session(space, machine, member, start, minutes=30):
    return MachineSession.objects.create(
        makerspace=space, machine=machine, machine_type=machine.machine_type, member=member, source="staff",
        started_at=start, ended_at=start + timedelta(minutes=minutes), duration_minutes=minutes)


def world(slug=None):
    slug = slug or f"facts-{uuid4().hex[:6]}"
    space = _space(slug, modules=MODULES, certifications=False)
    _features(space, FEATURES)
    laser = MachineType.objects.create(makerspace=space, slug=f"{slug}-laser", name="Laser")
    lathe = MachineType.objects.create(makerspace=space, slug=f"{slug}-lathe", name="Lathe")
    machine = Machine.objects.create(makerspace=space, machine_type=laser, name="Laser A")
    other = Machine.objects.create(makerspace=space, machine_type=lathe, name="Lathe A")
    resource = BookableSpace.objects.create(makerspace=space, name="Laser time",
                                            approval_mode=BookableSpace.ApprovalMode.INSTANT)
    booker, membership = _member(space, f"{slug}-booker")
    start = timezone.now() + timedelta(days=1)
    booking = create_booking(resource, member=booker, actor=booker, starts_at=start, ends_at=start + timedelta(hours=2))
    # Link the machine after booking so the time-booking gate is not under test here.
    BookableSpace.objects.filter(pk=resource.pk).update(machine=machine, machine_type=laser)
    event = Event.objects.create(makerspace=space, title="Open night", starts_at=start,
                                 ends_at=start + timedelta(hours=2))
    manager = make_member(f"{slug}-mgr", space)
    return SimpleNamespace(space=space, laser=laser, lathe=lathe, machine=machine, other=other, resource=resource,
                           booker=booker, membership=membership, booking=booking, event=event, start=start,
                           manager=manager)


def _register(w, n, status, member=None):
    return EventRegistration.objects.create(event=w.event, member=member, name=f"Person {n}",
                                            email=f"p{n}-{w.space.slug}@example.test", phone="1", status=status)


def _counts():
    return (EventRegistration.objects.count(), EventCheckInEvent.objects.count(), PresenceSession.objects.count(),
            BookingCheckInEvent.objects.count(), MachineSession.objects.count())


def test_event_facts_are_independent_and_read_only():
    w = world()
    walker, _ = _member(w.space, f"{w.space.slug}-walker")
    _register(w, 1, "registered")
    present_only = _register(w, 2, "registered", member=walker)
    attended = _register(w, 3, "attended")
    EventCheckInEvent.objects.create(makerspace=w.space, event=w.event, registration=attended, source="legacy",
                                     attended_at=w.start)
    _presence(w.space, walker, w.start + timedelta(minutes=10))          # inside the window
    _presence(w.space, w.booker, w.start - timedelta(hours=3), 60)       # ended before the event
    before = _counts()
    data = event_facts(w.manager, w.space.pk, w.event.pk)
    assert _counts() == before
    present_only.refresh_from_db()
    assert present_only.status == "registered"  # presence never implies attendance
    assert data["registrations"]["source"] == "events.EventRegistration"
    assert data["registrations"]["by_status"]["registered"] == 2
    assert data["registrations"]["by_status"]["attended"] == 1
    assert data["attendance"] == {
        "source": "events.EventCheckInEvent", "attended_registrations": 1, "check_in_records": 1,
        "registrations_with_check_in": 1, "check_in_records_by_source": {"legacy": 1}}
    presence = data["presence"]
    assert presence["source"] == "presence.PresenceSession"
    assert presence["sessions_overlapping"] == 1 and presence["distinct_people"] == 1
    assert presence["sessions_linked_to_event"] == 0
    assert walker.username not in str(data)


def test_booking_facts_are_independent_and_read_only():
    w = world()
    _presence(w.space, w.booker, w.start + timedelta(minutes=5), membership=w.membership)
    _machine_session(w.space, w.machine, w.booker, w.start + timedelta(minutes=10))
    _machine_session(w.space, w.machine, w.manager, w.start - timedelta(hours=4))  # outside
    _machine_session(w.space, w.other, w.booker, w.start + timedelta(minutes=10))  # another machine
    before = _counts()
    data = booking_facts(w.manager, w.space.pk, w.booking.pk)
    assert _counts() == before
    w.booking.refresh_from_db()
    assert w.booking.arrived_at is None  # presence and machine use never record an arrival
    assert data["arrival"]["source"] == "bookings.BookingCheckInEvent"
    assert data["arrival"]["arrived_at"] is None and data["arrival"]["arrival_confirmations"] == 0
    assert data["presence"]["subject_person_presence"] == "recorded"
    sessions = data["machine_sessions"]
    assert sessions["source"] == "machines.MachineSession" and sessions["machine_id"] == w.machine.pk
    assert sessions["sessions_overlapping"] == 1 and sessions["sessions"][0]["by_subject_person"] is True
    assert w.booker.username not in str(data) and w.booker.email not in str(data)


@pytest.mark.parametrize(("show_names", "allow_opt_out", "hidden", "expected"), [
    (True, True, True, "withheld"),
    (False, True, False, "withheld"),
    (True, False, True, "recorded"),
    (True, True, False, "recorded"),
])
def test_booker_presence_respects_display_privacy(show_names, allow_opt_out, hidden, expected):
    w = world()
    PresenceSettings.objects.create(makerspace=w.space, show_names=show_names, allow_personal_opt_out=allow_opt_out)
    PresencePreference.objects.create(makerspace=w.space, account=w.booker, hide_on_display=hidden)
    _presence(w.space, w.booker, w.start + timedelta(minutes=5), membership=w.membership, hidden=hidden)
    presence = booking_facts(w.manager, w.space.pk, w.booking.pk)["presence"]
    assert presence["subject_person_presence"] == expected
    assert presence["sessions_overlapping"] == 1  # opted-out people still count


def _booking_grant(w, user, permission):
    return BookingSpaceStaffGrant.objects.create(makerspace=w.space, space=w.resource, user=user,
                                                 granted_by=w.manager, permissions=[permission])


def test_each_booking_section_has_its_own_authority():
    w = world()
    _machine_session(w.space, w.machine, w.booker, w.start + timedelta(minutes=10))
    scanner = make_user(f"{w.space.slug}-scanner", access_status="active")
    _booking_grant(w, scanner, "check_in")
    data = booking_facts(scanner, w.space.pk, w.booking.pk)
    assert set(data) == {"subject", "arrival"}  # no presence or machine authority
    laser_mgr, _ = staff_for_actions(w.space, f"{w.space.slug}-laser", (Action.MANAGE_MACHINES,), machine_types=[w.laser])
    _booking_grant(w, laser_mgr, "edit_details")
    data = booking_facts(laser_mgr, w.space.pk, w.booking.pk)
    assert set(data) == {"subject", "machine_sessions"}
    lathe_mgr, _ = staff_for_actions(w.space, f"{w.space.slug}-lathe", (Action.MANAGE_MACHINES,), machine_types=[w.lathe])
    _booking_grant(w, lathe_mgr, "edit_details")
    with pytest.raises(NotFound):  # booking visible, but no section reachable: the view does not exist
        booking_facts(lathe_mgr, w.space.pk, w.booking.pk)
    with pytest.raises(PermissionDenied):  # machine reach alone never grants the booking
        booking_facts(staff_for_actions(w.space, f"{w.space.slug}-bare", (Action.MANAGE_MACHINES,),
                                        machine_types=[w.laser])[0], w.space.pk, w.booking.pk)


def test_each_event_section_has_its_own_authority():
    w = world()
    checker = make_user(f"{w.space.slug}-checker", access_status="active")
    create_manual_grant(makerspace=w.space, event=w.event, user=checker, permissions=["check_in"])
    assert set(event_facts(checker, w.space.pk, w.event.pk)) == {"subject", "attendance"}
    editor = make_user(f"{w.space.slug}-editor", access_status="active")
    create_manual_grant(makerspace=w.space, event=w.event, user=editor, permissions=["edit_details"])
    with pytest.raises(NotFound):
        event_facts(editor, w.space.pk, w.event.pk)


def test_sections_disappear_with_their_module_or_feature():
    w = world()
    _modules(w.space, remove=("presence",))
    _features(w.space, remove=("machines.sessions",))
    assert set(booking_facts(w.manager, w.space.pk, w.booking.pk)) == {"subject", "arrival"}
    assert set(event_facts(w.manager, w.space.pk, w.event.pk)) == {"subject", "registrations", "attendance"}
    _features(w.space, remove=("bookings.checkin",))
    with pytest.raises(NotFound):
        booking_facts(w.manager, w.space.pk, w.booking.pk)
    _modules(w.space, remove=("events",))
    with pytest.raises(APIException):
        event_facts(w.manager, w.space.pk, w.event.pk)


def test_routes_refuse_cross_tenant_access():
    w, other = world(), world()
    client = APIClient()
    client.force_authenticate(other.manager)
    own = reverse("admin-related-facts-booking", kwargs={"makerspace_id": other.space.pk, "booking_id": other.booking.pk})
    assert client.get(own).status_code == 200
    foreign_id = reverse("admin-related-facts-booking", kwargs={"makerspace_id": other.space.pk, "booking_id": w.booking.pk})
    assert client.get(foreign_id).status_code == 404
    foreign_space = reverse("admin-related-facts-event", kwargs={"makerspace_id": w.space.pk, "event_id": w.event.pk})
    assert client.get(foreign_space).status_code in (403, 404)
    assert Booking.objects.filter(pk=w.booking.pk, arrived_at__isnull=True).exists()

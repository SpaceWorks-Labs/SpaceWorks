"""P2-1: an event may link machine-time bookings for workshop machines beside its one room link."""
from datetime import timedelta
from uuid import uuid4

import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.bookings import services_bookings
from apps.bookings.models import BookableSpace, Booking
from apps.bookings.staff_price_confirmation import preview
from apps.events import booking_decision_service
from apps.events.booking_calendar_labels import linked_event_labels
from apps.events.models import Event
from apps.events.models_booking_decision import EventBookingDecision
from apps.events.models_machine_booking_link import EventMachineBookingLink
from apps.machines.models import CertificationType, Machine, MachineType
from apps.payments.models import Payment
from tests.encryption.conftest import enabled_encryption
from tests.events.orders_helpers import l6_space, make_staff
from tests.fixed_roles.helpers import staff_account
from tests.payments.test_track3_booking_event_charging import bookable, member_with_phone

pytestmark = pytest.mark.django_db(transaction=True)


def world(slug, *, certifications=False):
    maker = l6_space(slug)
    maker.enabled_modules = sorted(set(maker.enabled_modules) | {"bookings", "machines"})
    features = {"charges.enabled", "charges.bookings", "machines.time_booking"}
    if certifications:
        features.add("machines.certifications")
    maker.enabled_features = sorted(set(maker.enabled_features) | features)
    maker.save(update_fields=["enabled_modules", "enabled_features"])
    staff, member = make_staff(maker), member_with_phone(slug + "-member", maker)
    start = timezone.now() + timedelta(days=2)
    event = Event.objects.create(makerspace=maker, title="Laser workshop", starts_at=start,
                                 ends_at=start + timedelta(hours=2), status=Event.Status.DRAFT)
    kinds = [MachineType.objects.create(makerspace=maker, slug=f"{name}-{uuid4().hex[:6]}", name=name)
             for name in ("laser", "cnc")]
    times = []
    for kind in kinds:
        machine = Machine.objects.create(makerspace=maker, machine_type=kind, name=f"{kind.name} A")
        times.append(BookableSpace.objects.create(
            makerspace=maker, name=f"{kind.name} A time", kind=BookableSpace.Kind.MACHINE, machine=machine,
            machine_type=kind, approval_mode=BookableSpace.ApprovalMode.INSTANT, payment_amount="5.00"))
    return maker, staff, member, event, kinds, times


def book(space, member, event):
    with enabled_encryption():
        return services_bookings.create_booking(space, starts_at=event.starts_at, ends_at=event.ends_at,
                                                member=member, actor=member)


def client_for(user):
    client = APIClient()
    client.force_authenticate(user)
    return client


def url(maker, event):
    return reverse("admin-event-workshop-machines", kwargs={"makerspace_id": maker.pk, "event_id": event.pk})


def link(client, maker, event, booking_id, **extra):
    with enabled_encryption():
        return client.post(url(maker, event), {"booking_id": booking_id, **extra}, format="json")


def listing(client, maker, event):
    with enabled_encryption():
        return client.get(url(maker, event))


def test_machine_booking_is_linked_listed_and_labelled_without_new_charges():
    maker, staff, member, event, _kinds, times = world("workshop-link")
    booking = book(times[0], member, event)
    payments = Payment.objects.filter(makerspace=maker).count()
    client = client_for(staff)
    response = link(client, maker, event, booking.pk)
    assert response.status_code == 201, response.data
    assert response.data["reservation_state"] == "confirmed" and response.data["machine_name"] == "laser A"
    assert link(client, maker, event, booking.pk).status_code == 200  # replay
    data = listing(client, maker, event).data
    assert [row["current_booking_id"] for row in data["results"]] == [booking.pk] and data["withheld"] == 0
    assert Payment.objects.filter(makerspace=maker).count() == payments  # linking raises nothing
    assert not Payment.objects.filter(makerspace=maker, subject_type="event_venue_fee").exists()
    assert linked_event_labels(staff, maker, [booking.pk])[booking.pk]["event_id"] == event.pk


def test_an_event_holds_its_room_link_and_several_machine_links_with_one_room_charge():
    maker, staff, member, event, _kinds, times = world("workshop-room")
    room = bookable(maker, amount="12.50")
    room_booking = book(room, member, event)
    with enabled_encryption():
        booking_decision_service.create_decision(
            staff, maker, event.pk, booking_id=room_booking.pk, operation_id=uuid4(), expected_generation=None,
            expected_revision=0, expected_events_epoch=maker.loan_context_generations["events"],
            expected_bookings_epoch=maker.loan_context_generations["bookings"])
    client = client_for(staff)
    for space in times:
        assert link(client, maker, event, book(space, member, event).pk).status_code == 201
    assert link(client, maker, event, room_booking.pk).status_code == 404  # a room is never a machine link
    assert EventBookingDecision.objects.filter(event=event).count() == 1
    assert EventMachineBookingLink.objects.filter(event=event).count() == 2
    room_charges = Payment.objects.filter(makerspace=maker, subject_type=Payment.SubjectType.BOOKING,
                                          subject_id=room_booking.pk)
    assert room_charges.count() == 1
    assert not Payment.objects.filter(makerspace=maker, subject_type="event_venue_fee").exists()


@__import__("pytest").mark.skip(reason="Decision 319: certification gating retired (machine access grants replace it); see tests/parity_0120/machine_access.")
def test_uncertified_booker_is_refused_unless_type_authority_overrides():
    maker, staff, member, event, kinds, times = world("workshop-cert", certifications=True)
    booking = book(times[0], member, event)  # admitted before the type required training
    CertificationType.objects.create(makerspace=maker, machine_type=kinds[0], name="Laser induction",
                                     is_required_for_service=True, is_required_for_booking=True)
    client = client_for(staff)
    refused = link(client, maker, event, booking.pk)
    assert refused.status_code == 403 and "certification_required" in str(refused.data)
    assert not EventMachineBookingLink.objects.exists()
    allowed = link(client, maker, event, booking.pk, certification_override_reason="Supervised by instructor")
    assert allowed.status_code == 201, allowed.data


def test_machine_manager_reaches_only_their_machine_types():
    maker, staff, member, event, kinds, times = world("workshop-scope")
    laser = book(times[0], member, event)
    wrong = staff_account(maker, f"cnc-mm-{uuid4().hex[:6]}", "event_manager", "booking_manager",
                          "machine_manager", machine_types=(kinds[1],))
    right = staff_account(maker, f"laser-mm-{uuid4().hex[:6]}", "event_manager", "booking_manager",
                          "machine_manager", machine_types=(kinds[0],))
    bookings_only = staff_account(maker, f"bk-{uuid4().hex[:6]}", "event_manager", "booking_manager")
    for actor in (wrong, bookings_only):
        assert link(client_for(actor), maker, event, laser.pk).status_code == 404
    assert not EventMachineBookingLink.objects.exists()
    assert link(client_for(right), maker, event, laser.pk).status_code == 201
    hidden = listing(client_for(wrong), maker, event).data
    assert hidden["results"] == [] and hidden["withheld"] == 1


@pytest.mark.parametrize("module", ["bookings", "machines", "events"])
def test_module_off_leaves_no_surface(module):
    maker, staff, member, event, _kinds, times = world("workshop-off-" + module)
    booking = book(times[0], member, event)
    maker.enabled_modules = [key for key in maker.enabled_modules if key != module]
    maker.save(update_fields=["enabled_modules"])
    client = client_for(staff)
    assert listing(client, maker, event).status_code == 404
    assert link(client, maker, event, booking.pk).status_code == 404
    assert not EventMachineBookingLink.objects.exists()


def test_cross_tenant_staff_and_bookings_are_refused():
    maker, staff, member, event, _kinds, times = world("workshop-tenant")
    other_maker, other_staff, other_member, other_event, _other_kinds, other_times = world("workshop-tenant-b")
    booking = book(times[0], member, event)
    foreign = book(other_times[0], other_member, other_event)
    assert link(client_for(other_staff), maker, event, booking.pk).status_code in (403, 404)
    assert listing(client_for(other_staff), maker, event).status_code in (403, 404)
    assert link(client_for(staff), maker, event, foreign.pk).status_code == 404
    assert not EventMachineBookingLink.objects.exists()


def test_cancelled_machine_booking_is_replaced_and_the_link_keeps_the_original():
    maker, staff, member, event, _kinds, times = world("workshop-replace")
    booking = book(times[0], member, event)
    client = client_for(staff)
    link_id = link(client, maker, event, booking.pk).data["link_id"]
    with enabled_encryption():
        services_bookings.cancel_booking(booking, actor=staff)
        shown = preview(times[1], member, booking.starts_at, booking.ends_at)
    assert listing(client, maker, event).data["results"][0]["replaceable"] is True
    path = reverse("admin-event-workshop-machine-replacement",
                   kwargs={"makerspace_id": maker.pk, "event_id": event.pk, "link_id": link_id})
    with enabled_encryption():
        response = client.post(path, {
            "expected_booking_id": booking.pk, "space_id": times[1].pk, "member_id": member.pk,
            "starts_at": booking.starts_at.isoformat(), "ends_at": booking.ends_at.isoformat(),
            "price_confirmation": shown["price_confirmation"]}, format="json")
    assert response.status_code == 201, response.data
    replacement = Booking.objects.get(pk=response.data["booking_id"])
    assert replacement.replaces_id == booking.pk
    row = listing(client, maker, event).data["results"][0]
    assert row["booking_id"] == booking.pk and row["current_booking_id"] == replacement.pk
    assert row["history"] == [{"booking_id": booking.pk, "status": "cancelled"}]
    assert linked_event_labels(staff, maker, [replacement.pk])[replacement.pk]["event_id"] == event.pk


def test_workshop_machine_link_is_classified_portable_and_tenant_scoped():
    from apps.data_export.classification import EXPORTED_MODEL_FIELDS
    from apps.tenant_migration.tenant_dump_model_catalog import PROJECTED_MODEL_LABELS
    from apps.tenant_rls.policies import build_plans
    from apps.tenant_rls.scope_registry import predicates
    label = "events.EventMachineBookingLink"
    assert EXPORTED_MODEL_FIELDS[label].split() == ["id", "makerspace", "event", "booking", "created_at", "unlinked_at"]
    assert label in PROJECTED_MODEL_LABELS
    scope = predicates()[label]
    assert scope.any_paths == ("makerspace",) and not scope.includes({"makerspace": 2}, 1)
    plans, unresolvable = build_plans()
    assert label in plans and label not in unresolvable

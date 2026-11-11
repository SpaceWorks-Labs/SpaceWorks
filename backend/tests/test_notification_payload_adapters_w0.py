"""Domain adapters preserve subject identity without leaking template contacts."""
from datetime import timedelta
from types import SimpleNamespace as NS

import pytest
from django.utils import timezone

from apps.bookings import notifications as bookings
from apps.events import notifications as events
from apps.hardware_requests import notifications as hardware
from apps.hardware_requests.models import HardwareRequest
from apps.integrations.lifecycle_data import lifecycle_data
from apps.integrations.models_contract import NotificationEnvelope
from apps.machines import service_printing_emails as printing
from apps.machines.models import Machine
from apps.maintenance import notifications as maintenance
from apps.maintenance.models import MaintenanceLog, MaintenanceSchedule
from apps.makerspaces import membership_notifications as members
from apps.makerspaces.models import MakerspaceMembership, MembershipRequest
from tests.machines.certification_helpers import _machine_type
from tests.test_notification_families_f3 import family_world

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def no_broker(monkeypatch):
    monkeypatch.setattr("apps.integrations.notification_outbox.enqueue", lambda pk: None)


def test_hardware_adapter_identifies_request_and_charge():
    space, manager, owner, payment = family_world("adapter-hardware")
    row = HardwareRequest.objects.create(makerspace=space, requester=owner,
        requester_username=owner.username, status="accepted", accepted_by=manager)
    hardware.notify_request_accepted(row)
    envelope = NotificationEnvelope.objects.get(source_kind="hardware.request", recipient=owner)
    assert envelope.source_id == str(row.pk) and envelope.context["request_id"] == row.pk
    hardware.notify_loan_charge(row, "deposit_raised", payment)
    charge = NotificationEnvelope.objects.get(source_kind="hardware.charge", recipient=manager)
    assert charge.context == {"request_id": row.pk, "payment_id": payment.pk}
    assert charge.source_id == str(payment.pk)


def test_booking_adapter_identifies_booking_and_space(monkeypatch):
    from apps.bookings.models import BookableSpace, Booking
    space, _manager, owner, _ = family_world("adapter-booking")
    target = BookableSpace.objects.create(makerspace=space, name="Studio")
    start = timezone.now() + timedelta(hours=1)
    row = Booking.objects.create(space=target, member=owner, name="Private booker",
        email=owner.email, phone="123", starts_at=start, ends_at=start+timedelta(hours=1), status="confirmed")
    payloads = []
    monkeypatch.setattr(bookings, "notify_lifecycle", lambda ms, **kw: payloads.append(kw["build"]()))
    bookings.notify_booking_status(row, "confirmed")
    assert payloads[0].data == {"booking_id": row.pk, "space_id": target.pk}
    assert payloads[0].context["booking"].name == "Private booker"
    envelope = NotificationEnvelope.objects.get(source_kind="bookings.lifecycle", recipient=owner)
    assert envelope.context["booking_id"] == row.pk and envelope.context["space_id"] == target.pk
    assert "email" not in envelope.context


def test_event_adapter_identifies_occurrence_series_and_registration(monkeypatch):
    from apps.events.models import EventRegistration
    from tests.events.test_services import make_event
    space, _manager, owner, _ = family_world("adapter-event")
    event = make_event(space)
    registration = EventRegistration.objects.create(event=event, member=owner,
        name="Private registrant", email=owner.email, phone="123")
    payloads = []
    monkeypatch.setattr(events, "notify_lifecycle", lambda ms, **kw: payloads.append(kw["build"]()))
    events.notify_event_lifecycle(event, "registration_approved", registration.pk)
    assert payloads[0].data == {"event_id": event.pk, "series_id": event.series_id,
                              "registration_id": registration.pk}
    envelope = NotificationEnvelope.objects.get(source_kind="events.lifecycle", recipient=owner)
    assert envelope.context["event_id"] == event.pk
    assert envelope.context["registration_id"] == registration.pk
    assert "email" not in envelope.context


def test_maintenance_adapter_identifies_machine_schedule_and_completion_log():
    space, manager, _owner, _ = family_world("adapter-maintenance")
    machine = Machine.objects.create(makerspace=space, machine_type=_machine_type(space), name="Laser")
    schedule = MaintenanceSchedule.objects.create(machine=machine, description="Clean",
        interval_days=7, next_due=timezone.now().date(), created_by=manager)
    log = MaintenanceLog.objects.create(machine=machine, performed_by=manager, summary="Cleaned")
    maintenance.notify_maintenance_lifecycle(schedule, "schedule_completed", log_id=log.pk)
    envelope = NotificationEnvelope.objects.get(source_kind="machines.maintenance", recipient=manager)
    assert envelope.source_id == str(schedule.pk)
    assert {key: envelope.context[key] for key in ("machine_id", "schedule_id", "maintenance_log_id")} == {
        "machine_id": machine.pk, "schedule_id": schedule.pk, "maintenance_log_id": log.pk}


def test_membership_adapters_identify_request_and_membership():
    space, manager, owner, _ = family_world("adapter-members")
    request = MembershipRequest.objects.create(makerspace=space, user=owner,
        invite_email=owner.email, state="requested")
    members.notify_membership_request_pending(request)
    application = NotificationEnvelope.objects.get(source_kind="membership.application", recipient=owner)
    assert application.source_id == str(request.pk) and application.subject_id == str(request.pk)
    membership = MakerspaceMembership.objects.get(makerspace=space, user=owner)
    members.notify_member_joined(membership)
    joined = NotificationEnvelope.objects.get(source_kind="membership.lifecycle", recipient=manager)
    assert joined.source_id == str(membership.pk) and joined.subject_id == str(membership.pk)


def test_printing_adapter_identifies_kernel_request():
    from tests.test_b7a_kernel_emails import _printer_request
    _space, request, owner, _staff = _printer_request("adapter-printing")
    printing.notify_printer_service_status(request, "accepted")
    envelope = NotificationEnvelope.objects.get(source_kind="machines.service", recipient=owner)
    assert envelope.source_id == str(request.pk)
    assert envelope.context == {"machine_service_request_id": request.pk}


def test_structured_ids_refuse_contact_credentials_and_invalid_identifiers():
    assert lifecycle_data({
        "request_id": 12, "email": "private@example.test", "secret": "private",
        "booking_id": True, "event_id": "13", "series_id": -1, "payment_id": None,
    }) == {"request_id": 12}

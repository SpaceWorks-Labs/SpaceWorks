"""Area C facts with deliberately populated forbidden disclosure fields."""

from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import patch

import pytest

from apps.bookings.models import BookableSpace, Booking
from apps.devices.models import Device, DeviceCommand, PrinterJob
from apps.machines.models import Machine, MachineErrorLog, MachineServiceRequest, MachineStatusEvent, MachineType, MachineUsageEntry, ServiceBucket
from apps.maintenance.models import MaintenanceLog, MaintenanceSchedule
from apps.warranty.models import Warranty
from tests.fixed_roles.helpers import staff_account
from tests.return_helpers import make_space, make_user


def at(day=12, hour=9, minute=0):
    return datetime(2026, 10, day, hour, minute, tzinfo=timezone.utc)


def job(machine, member, *, status="completed", day=12, actual=60):
    bucket, _ = ServiceBucket.objects.get_or_create(machine=machine, name="Queue")
    with patch("django.utils.timezone.now", return_value=at(day, 6)):
        return MachineServiceRequest.objects.create(
            makerspace=machine.makerspace, bucket=bucket, assigned_machine=machine,
            requester=member, member=member, title="Private job", status=status,
            requester_name="private person", contact_email="private@example.test",
            accepted_at=at(day, 7), started_at=at(day, 9),
            completed_at=at(day, 10) if status == "completed" else None,
            failed_at=at(day, 10) if status == "failed" else None,
            collected_at=at(day, 11) if status == "completed" else None,
            actual_minutes=actual, estimated_minutes=240, fail_percent_complete=25,
        )


def manual(machine, *, member=None, day=12, started=True, hours="2"):
    row = MachineUsageEntry(
        machine=machine, member=member, hours=Decimal(hours),
        started_at=at(day, 9, 30) if started else None, created_at=at(day, 15),
        note="private note", contact_email="private@example.test",
    )
    row.save(preserve_created_at=True)
    return row


def seed(machine, member):
    completed = job(machine, member)
    job(machine, member, status="failed", actual=15)
    manual(machine, member=member)
    manual(machine, started=False, hours="3")
    room = BookableSpace.objects.create(makerspace=machine.makerspace, name="Machine booking", machine_type=machine.machine_type)
    Booking.objects.create(space=room, member=member, name="Private", email="private@example.test", phone="12345",
                           starts_at=at(12, 9), ends_at=at(12, 12), status="confirmed")
    with patch("django.utils.timezone.now", return_value=at(12, 9)):
        MachineErrorLog.objects.create(machine=machine, severity="critical", message="private internal diagnostic")
        MachineStatusEvent.objects.create(makerspace=machine.makerspace, machine=machine,
                                          from_status="idle", to_status="maintenance", source="manual")
    MaintenanceLog.objects.create(machine=machine, performed_at=at(12, 9), summary="private summary", cost=Decimal("12.50"))
    MaintenanceSchedule.objects.create(machine=machine, description="Quarterly", interval_days=90, next_due=at(11).date())
    Warranty.objects.create(makerspace=machine.makerspace, machine=machine, warranty_expires_on=at(18).date(), vendor_contact="private@example.test")
    device = Device.objects.create(makerspace=machine.makerspace, name="Printer device", kind="printer")
    command = DeviceCommand.objects.create(makerspace=machine.makerspace, device=device, device_key_version=1)
    PrinterJob.objects.create(command=command, makerspace=machine.makerspace, device=device, machine=machine,
                              service_request=completed, machine_id_snapshot=machine.pk, machine_name=machine.name,
                              service_request_id_snapshot=completed.pk, service_request_name="private request",
                              external_job_id="private external reference", created_at=at(12, 9), state="needs_review")


@pytest.fixture
def c_lab():
    space = make_space("c-analytics")
    foreign = make_space("c-foreign")
    for tenant in (space, foreign):
        tenant.timezone = "UTC"
        # 0.12.0 (module on/off audit): the session and maintenance reports sit behind their capabilities.
        tenant.enabled_features = sorted(set(tenant.enabled_features or []) | {"machines.sessions", "machines.maintenance"})
        tenant.save(update_fields=["timezone", "enabled_features"])
    member = make_user("c-member", access_status="active")
    laser_type = MachineType.objects.create(makerspace=space, slug="laser", name="Laser")
    printer_type = MachineType.objects.create(makerspace=space, slug="printer", name="Printer")
    foreign_type = MachineType.objects.create(makerspace=foreign, slug="foreign", name="Foreign")
    laser = Machine.objects.create(makerspace=space, machine_type=laser_type, name="Laser one")
    printer = Machine.objects.create(makerspace=space, machine_type=printer_type, name="Printer two")
    other = Machine.objects.create(makerspace=foreign, machine_type=foreign_type, name="Foreign machine")
    Machine.objects.filter(pk__in=[laser.pk, printer.pk, other.pk]).update(created_at=at(1))
    manager = staff_account(space, "c-machine-manager", "machine_manager", machine_types=[laser_type])
    owner = staff_account(space, "c-owner", "space_manager")
    inventory = staff_account(space, "c-inventory", "inventory_manager")
    for machine in (laser, printer, other):
        seed(machine, member)
    return dict(space=space, foreign=foreign, member=member, manager=manager, owner=owner, inventory=inventory,
                laser=laser, printer=printer, other=other, date_range=(at(12, 0), at(19, 0)))

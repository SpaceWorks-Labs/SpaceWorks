from datetime import timedelta
from types import SimpleNamespace

import pytest
from django.utils import timezone

from apps.integrations.models_contract import NotificationEnvelope
from apps.integrations.notification_sources import source_eligible
from apps.machines.models import CertificationType, CertificationGrant, MachineType, Machine
from apps.machines.notifications_p2_certifications import notify, notify_digest
from apps.machines.notifications_p2_maintenance import notify as maintenance
from apps.makerspaces.models import MakerspaceMembership

pytestmark = pytest.mark.django_db


def grant(world):
    member = MakerspaceMembership.objects.create(makerspace=world.space, user=world.owner,
        role=MakerspaceMembership.Role.CUSTOM, assigned_role=world.space.roles.get(slug="member"))
    machine_type = MachineType.objects.create(makerspace=world.space, slug="laser", name="Laser")
    certification = CertificationType.objects.create(makerspace=world.space, machine_type=machine_type, name="Induction")
    return CertificationGrant.objects.create(certification_type=certification, membership=member,
        granted_by=world.manager, expires_at=timezone.now() + timedelta(days=1))


@pytest.mark.parametrize("event", ["granted", "revoked", "expiring", "expired"])
def test_certification_coverage(equipment, event):
    row = grant(equipment)
    if event == "revoked":
        row.revoked_by, row.revoked_at = equipment.manager, timezone.now()
        row.save(update_fields=["revoked_by", "revoked_at"])
    if event == "expired":
        row.expires_at = timezone.now() - timedelta(hours=1)
        row.save(update_fields=["expires_at"])
    include_staff = event in {"granted", "revoked"}
    assert notify(row, event, include_staff=include_staff).scheduled
    envelopes = NotificationEnvelope.objects.filter(source_kind="machines.certification")
    own = envelopes.get(audience="requester")
    assert own.recipient_id == equipment.owner.pk
    assert envelopes.filter(audience="staff").exists() == include_staff
    assert own.scope["machine_type_id"] == row.certification_type.machine_type_id
    assert row.notes not in str(own.context) if row.notes else True
    if event in {"granted", "revoked"}:
        assert source_eligible(own)


def test_certification_daily_digest_coverage(equipment):
    from apps.machines.models_policy import MakerspaceMachineTypePolicy
    row = grant(equipment)
    # Explicit reminder window avoids reliance on a deployment's default policy.
    MakerspaceMachineTypePolicy.objects.create(makerspace=equipment.space,
        machine_type=row.certification_type.machine_type, cert_reminder_days=7)
    day = timezone.now().date().isoformat()
    reminder = SimpleNamespace(subject=f"{row.certification_type.machine_type_id}:{day}")
    assert notify_digest(equipment.space, reminder, SimpleNamespace(title="Expiry", body="Review induction")).scheduled
    assert set(NotificationEnvelope.objects.filter(source_kind="machines.certification_summary").values_list("audience", flat=True)) == {"staff"}


@pytest.mark.parametrize("event", ["schedule_created", "schedule_updated", "schedule_deactivated", "logged", "schedule_completed", "due_soon", "overdue"])
def test_maintenance_coverage(equipment, event):
    from apps.maintenance.models import MaintenanceLog, MaintenanceSchedule
    machine_type = MachineType.objects.create(makerspace=equipment.space, slug="mill", name="Mill")
    machine = Machine.objects.create(makerspace=equipment.space, machine_type=machine_type, name="Mill")
    if event == "logged":
        row = MaintenanceLog.objects.create(machine=machine, performed_by=equipment.manager, summary="Inspection")
    else:
        row = MaintenanceSchedule.objects.create(machine=machine, description="Inspection", interval_days=7,
            next_due=timezone.now().date(), created_by=equipment.manager, is_active=event != "schedule_deactivated")
    assert maintenance(row, event).scheduled
    envelope = NotificationEnvelope.objects.get(source_kind="machines.maintenance")
    assert envelope.audience == "staff" and envelope.recipient_id == equipment.manager.pk
    assert envelope.scope["machine_id"] == machine.pk


def test_usage_meter_maintenance_coverage(equipment):
    from apps.maintenance.models import MaintenanceSchedule
    machine_type = MachineType.objects.create(makerspace=equipment.space, slug="metered", name="Metered")
    machine = Machine.objects.create(makerspace=equipment.space, machine_type=machine_type, name="Metered")
    row = MaintenanceSchedule.objects.create(machine=machine, description="Inspection", interval_days=7,
        next_due=timezone.now().date(), created_by=equipment.manager, trigger="usage", job_count=1)
    assert maintenance(row, "overdue", due_reason="Usage-based maintenance is due.").scheduled
    assert NotificationEnvelope.objects.get(source_kind="machines.maintenance").context["meter"]

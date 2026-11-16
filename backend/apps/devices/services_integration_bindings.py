"""Staff management of per-type integration bindings and the read-only status list.

Every write is audited in the space (``devices.integration_bound`` / ``_updated`` /
``_unbound``). A binding is created disabled unless staff say otherwise, and only the
reserved ``printer_agent`` kind exists; it needs the built-in printer type.
"""
from django.utils.translation import gettext
from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import NotFound, ValidationError

from apps.accounts import rbac
from apps.audit import services as audit
from apps.devices.errors_integrations import IntegrationConflict
from apps.devices.integration_access import authorize_type_staff
from apps.devices.models import MachineTypeIntegration, PrinterDeviceBinding
from apps.devices.services_locks import lock_tenant
from apps.machines.models import MachineType
from apps.machines.printer_capabilities import is_printer_type


def machine_type_for(actor, makerspace_id, type_id):
    machine_type = MachineType.objects.filter(pk=type_id).first()
    if machine_type is None:
        raise NotFound()
    authorize_type_staff(actor, makerspace_id, machine_type)
    return machine_type


def scoped_integration(actor, pk):
    row = rbac.scope_by_action(actor, rbac.Action.MANAGE_DEVICES, MachineTypeIntegration.objects.all()) \
        .select_related("machine_type").filter(pk=pk).first()
    if row is None:
        raise NotFound()
    authorize_type_staff(actor, row.makerspace_id, row.machine_type)
    return row


def create_integration(actor, makerspace_id, machine_type, *, kind, enabled, config_schema_version):
    if kind == MachineTypeIntegration.Kind.PRINTER_AGENT and not is_printer_type(machine_type):
        raise ValidationError({"kind": gettext("A printer agent binds only the built-in 3D printer type.")},
                              code="integration_kind_unsupported")
    try:
        with transaction.atomic():
            makerspace = lock_tenant(makerspace_id)
            row = MachineTypeIntegration.objects.create(
                makerspace=makerspace, machine_type=machine_type, kind=kind, enabled=enabled,
                config_schema_version=config_schema_version, created_by=actor)
            audit.record(actor, "devices.integration_bound", makerspace=row.makerspace, target=row, meta={
                "machine_type_id": row.machine_type_id, "kind": row.kind, "enabled": row.enabled,
                "config_schema_version": row.config_schema_version})
            return row
    except IntegrityError as exc:
        raise IntegrationConflict(gettext("This machine type already has that integration."),
                                  code="integration_exists") from exc


def update_integration(actor, pk, changes):
    scoped_integration(actor, pk)
    with transaction.atomic():
        row = get_object_or_404(MachineTypeIntegration.objects.select_for_update(), pk=pk)
        lock_tenant(row.makerspace_id)
        for field, value in changes.items():
            setattr(row, field, value)
        row.save(update_fields=[*changes, "updated_at"])
        audit.record(actor, "devices.integration_updated", makerspace=row.makerspace, target=row, meta={
            "machine_type_id": row.machine_type_id, "kind": row.kind, "enabled": row.enabled,
            "config_schema_version": row.config_schema_version})
        return row


def delete_integration(actor, pk):
    scoped_integration(actor, pk)
    with transaction.atomic():
        row = get_object_or_404(MachineTypeIntegration.objects.select_for_update(), pk=pk)
        lock_tenant(row.makerspace_id)
        audit.record(actor, "devices.integration_unbound", makerspace=row.makerspace, target=row, meta={
            "machine_type_id": row.machine_type_id, "kind": row.kind, "enabled": row.enabled,
            "config_schema_version": row.config_schema_version})
        row.delete()


def integration_status(makerspace_id, machine_type):
    """Read-only: every enabled printer binding on a machine of this type, with its snapshot."""
    bindings = PrinterDeviceBinding.objects.filter(
        makerspace_id=makerspace_id, enabled=True, machine__machine_type=machine_type,
    ).select_related("device", "device__status_snapshot", "machine").order_by("machine__name", "device_id")
    return [{
        "device_id": row.device_id, "device_name": row.device.name, "machine_id": row.machine_id,
        "machine_name": row.machine.name, "last_seen_at": row.device.last_seen_at,
        "snapshot": getattr(row.device, "status_snapshot", None),
    } for row in bindings]

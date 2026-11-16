"""Who may reach the machine-integration foundation, and on what (release 2 L10, #76).

Off by default: unless the makerspace has the `machines.integrations` capability (which
needs `devices`, `machines` and `machine_service`), every integration route answers 404,
for staff and devices alike, before any other check, so a disabled space reveals nothing.

A device reaches the integration routes only as an ACTIVE printer whose enabled printer
binding names an active machine whose type carries an ENABLED `printer_agent` binding in
the same makerspace. That chain is resolved under the caller's locks every time.
"""

from django.utils.translation import gettext
from rest_framework.exceptions import NotFound, PermissionDenied

from apps.accounts import rbac
from apps.devices.models import Device, MachineTypeIntegration, PrinterDeviceBinding
from apps.machines.models import Machine
from apps.machines.role_scope import covers_type

FEATURE_KEY = "machines.integrations"
REQUIRED_MODULES = ("devices", "machines", "machine_service")


def integrations_enabled(makerspace_id):
    from apps.makerspaces.models import Makerspace
    from apps.makerspaces.platform import feature_enabled, module_enabled

    space = Makerspace.objects.filter(pk=makerspace_id).first()
    if space is None:
        return False
    return all(module_enabled(space, key) for key in REQUIRED_MODULES) and feature_enabled(space, FEATURE_KEY)


def require_integrations(makerspace_id):
    if not integrations_enabled(makerspace_id):
        raise NotFound()


def authorize_type_staff(actor, makerspace_id, machine_type):
    """Staff need MANAGE_DEVICES in the space and a machine scope that covers the type."""
    require_integrations(makerspace_id)
    if not rbac.can(actor, rbac.Action.MANAGE_DEVICES, makerspace_id):
        raise PermissionDenied()
    if machine_type.makerspace_id not in (None, makerspace_id):
        raise NotFound()
    if not covers_type(actor, makerspace_id, machine_type):
        raise PermissionDenied(gettext("Machine type is outside your management scope."))


def device_binding(device, *, lock=False):
    """(binding, machine, integration) for an integrated printer device, else 404.

    With ``lock`` the machine then the binding are row-locked, the order the printer
    adapter uses after the request (request -> machine -> binding), and re-checked.
    """
    require_integrations(device.makerspace_id)
    if device.kind != Device.Kind.PRINTER or device.status != Device.Status.ACTIVE:
        raise NotFound()
    binding = PrinterDeviceBinding.objects.filter(device=device, makerspace_id=device.makerspace_id,
                                                  enabled=True, machine__isnull=False).first()
    if binding is None:
        raise NotFound()
    machines = Machine.objects.filter(pk=binding.machine_id, makerspace_id=device.makerspace_id, is_active=True)
    machine = (machines.select_for_update(no_key=True) if lock else machines).first()
    if machine is None:
        raise NotFound()
    if lock:
        binding = PrinterDeviceBinding.objects.select_for_update().filter(
            pk=binding.pk, enabled=True, machine_id=machine.pk).first()
        if binding is None:
            raise NotFound()
    integration = MachineTypeIntegration.objects.filter(
        makerspace_id=device.makerspace_id, machine_type_id=machine.machine_type_id,
        kind=MachineTypeIntegration.Kind.PRINTER_AGENT, enabled=True,
    ).first()
    if integration is None:
        raise NotFound()
    return binding, machine, integration

"""Who may reach the Device Adapter API, and on what (decisions 310-312).

Off by default: unless the makerspace has the `machines.integrations` switch (which needs `devices`,
`machines` and `machine_service`) every adapter route answers 404, for staff and adapters alike, before any
other check. A capability's child switch (`machines.integrations.access|usage_billing|video`) is checked the
same way. Cross-tenant ids are always 404, never 403.
"""
from django.utils.translation import gettext
from rest_framework.exceptions import NotFound, PermissionDenied

from apps.accounts import rbac
from apps.devices.adapters.registry import CAPABILITIES
from apps.devices.integration_access import FEATURE_KEY, REQUIRED_MODULES
from apps.devices.models import AdapterBinding, AdapterProfile, Device
from apps.devices.services_locks import lock_tenant

ACCESS_SWITCH = "machines.integrations.access"
USAGE_SWITCH = "machines.integrations.usage_billing"
VIDEO_SWITCH = "machines.integrations.video"
KIOSK_SWITCH = "machines.integrations.kiosk"
RECORDING_SWITCH = "machines.integrations.recording"
AUDIO_SWITCH = "machines.integrations.audio"
TALK_SWITCH = "machines.integrations.talk"
AUDIO_RECORDING_SWITCH = "machines.integrations.audio_recording"
ARTIFACTS_SWITCH = "machines.integrations.artifacts"
DETECTIONS_SWITCH = "machines.integrations.detections"
HISTORY_SWITCH = "machines.integrations.telemetry_history"
DIAGNOSTICS_SWITCH = "machines.integrations.diagnostics"
OFFLINE_SWITCH = "machines.integrations.offline_cache"
CHILD_SWITCHES = (AUDIO_SWITCH, TALK_SWITCH, AUDIO_RECORDING_SWITCH, ARTIFACTS_SWITCH, DETECTIONS_SWITCH, HISTORY_SWITCH,
                  DIAGNOSTICS_SWITCH, OFFLINE_SWITCH, ACCESS_SWITCH, USAGE_SWITCH, VIDEO_SWITCH, KIOSK_SWITCH, RECORDING_SWITCH)


def adapters_enabled(makerspace_id, child=None):
    from apps.makerspaces.models import Makerspace
    from apps.makerspaces.platform import feature_enabled, module_enabled

    space = Makerspace.objects.filter(pk=makerspace_id).first()
    if space is None or not all(module_enabled(space, key) for key in REQUIRED_MODULES):
        return False
    return feature_enabled(space, FEATURE_KEY) and (child is None or feature_enabled(space, child))


def require_adapters(makerspace_id, child=None):
    if not adapters_enabled(makerspace_id, child):
        raise NotFound()


def switch_for(capability):
    cap = CAPABILITIES.get(capability)
    return (cap.switch or None) if cap else None


def adapter_device(principal, *, lock=False):
    """The active adapter Device (and its tenant) behind a signed principal, else 404/403."""
    require_adapters(principal.makerspace_id)
    if lock:
        lock_tenant(principal.makerspace_id)
    devices = Device.objects.filter(pk=principal.device_id, makerspace_id=principal.makerspace_id)
    device = (devices.select_for_update() if lock else devices).first()
    if device is None or device.kind != Device.Kind.ADAPTER:
        raise NotFound()
    if device.status != Device.Status.ACTIVE or device.key_version != principal.key_version:
        raise PermissionDenied(gettext("Device authorization is no longer active."))
    return device


def declared(device):
    profile = AdapterProfile.objects.filter(device=device).first()
    return {row["name"] for row in (profile.capabilities if profile else [])}


def binding_for(device, binding_id, capability=None):
    """The adapter's own enabled binding that serves ``capability`` (404 for any other)."""
    switch = switch_for(capability) if capability else None
    if switch:
        require_adapters(device.makerspace_id, switch)
    binding = AdapterBinding.objects.filter(pk=binding_id, device=device, makerspace_id=device.makerspace_id,
                                            enabled=True).first()
    if binding is None or (capability and capability not in binding.capabilities):
        raise NotFound()
    return binding


def authorize_staff(actor, makerspace_id, machine=None, child=None):
    """MANAGE_DEVICES in the space plus, for a machine target, the actor's machine scope."""
    require_adapters(makerspace_id, child)
    if not rbac.can(actor, rbac.Action.MANAGE_DEVICES, makerspace_id):
        raise PermissionDenied()
    if machine is not None:
        from apps.machines.access import can_manage_machine
        if not can_manage_machine(actor, machine):
            raise PermissionDenied(gettext("Machine is outside your management scope."))


def scoped_adapter(actor, pk, *, whole=False):
    """An adapter Device inside the actor's MANAGE_DEVICES scope; anything else (other tenant, wrong kind) is 404.

    ``whole=True`` is for adapter-wide changes and reads (config push, the push webhook): they reach every target the
    adapter serves, so every machine binding must be inside the actor's machine scope (decision 336i, fails closed).
    """
    device = rbac.scope_by_action(actor, rbac.Action.MANAGE_DEVICES, Device.objects.all()).filter(
        pk=pk, kind=Device.Kind.ADAPTER).first()
    if device is None:
        raise NotFound()
    authorize_staff(actor, device.makerspace_id)
    if whole:
        from apps.machines.access import can_manage_machine
        rows = AdapterBinding.objects.filter(device=device, machine__isnull=False).select_related("machine")
        if any(not can_manage_machine(actor, row.machine) for row in rows):
            raise PermissionDenied(gettext("A machine this adapter serves is outside your management scope."))
    return device


def _unrestricted(actor, makerspace_id):
    """Machine scope does not narrow this actor here (Space Manager, superadmin): every row is theirs to read."""
    from apps.machines.role_scope_resolution import EXEMPT, manage_scope_for
    return (manage_scope_for(actor, makerspace_id) is EXEMPT
            and rbac.can(actor, rbac.Action.MANAGE_MACHINES, makerspace_id))


def visible_binding_ids(actor, device):
    """The adapter's bindings the actor may see, or ``None`` for all: a non-machine target, or a machine in scope."""
    if _unrestricted(actor, device.makerspace_id):
        return None
    from apps.machines.access import can_manage_machine
    rows = AdapterBinding.objects.filter(device=device).select_related("machine")
    return {row.pk for row in rows if row.machine is None or can_manage_machine(actor, row.machine)}


def visible_rows(actor, device, queryset):
    """An adapter's log, event or command rows narrowed to the actor's machine scope (decision 336i).

    A row whose binding is gone (unbound since) names no machine any more, so only an unrestricted actor sees it.
    """
    ids = visible_binding_ids(actor, device)
    return queryset if ids is None else queryset.filter(binding_id__in=ids)


def scoped_binding(actor, pk, child=None):
    binding = rbac.scope_by_action(actor, rbac.Action.MANAGE_DEVICES, AdapterBinding.objects.all()).select_related(
        "device", "machine").filter(pk=pk).first()
    if binding is None:
        raise NotFound()
    authorize_staff(actor, binding.makerspace_id, binding.machine, child=child)
    return binding

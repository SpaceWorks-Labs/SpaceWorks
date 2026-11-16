"""Staff-side adapter administration: bind and unbind targets, read an adapter's picture, logs.

Enrollment, revoke and key rotation reuse the existing device services (``services_identity`` /
``services_enrollment``); an adapter is just a Device of kind ``adapter``. Every mutation is RBAC-checked,
machine-scoped, tenant-locked and audited with the staff actor.
"""
from django.db import IntegrityError, transaction

from apps.audit import services as audit
from apps.devices.adapter_access import authorize_staff
from apps.devices.adapters.registry import CAPABILITIES
from apps.devices.models import AdapterBinding, AdapterCommand, AdapterEvent, AdapterProfile, AdapterStatus, Device
from apps.devices.services_adapter_core import AdapterError
from apps.devices.services_adapter_hello import binding_payload, bump_config
from apps.devices.services_adapter_safety import config_view
from apps.devices.services_locks import lock_tenant


def bind(actor, device, *, target_type, machine_id=None, target_id="", external_ref="", capabilities=()):
    from rest_framework.exceptions import NotFound
    machine = None
    if target_type == "machine":
        from apps.machines.models import Machine
        machine = Machine.objects.filter(pk=machine_id, makerspace_id=device.makerspace_id, is_active=True).first()
        if machine is None:
            raise NotFound()
    elif target_type in ("storage_location", "item", "box"):
        from apps.devices.services_adapter_locate import _target_exists
        if not _target_exists(device.makerspace_id, target_type, str(target_id)):
            raise NotFound()
    elif not target_id:
        target_id = external_ref or target_type  # door/space/machine_type need a stable opaque key
    authorize_staff(actor, device.makerspace_id, machine)
    declared = {row["name"] for row in getattr(getattr(device, "adapter_profile", None), "capabilities", [])}
    for name in capabilities:
        cap = CAPABILITIES.get(name)
        if cap is None or target_type not in cap.targets:
            raise AdapterError("capability_target_mismatch", "That capability cannot serve this target type.")
        if declared and name not in declared:
            raise AdapterError("capability_not_declared", "The adapter did not declare that capability in its hello.",
                               status_code=409)
    try:
        with transaction.atomic():
            makerspace = lock_tenant(device.makerspace_id)
            locked = Device.objects.select_for_update().get(pk=device.pk)
            if locked.status == Device.Status.REVOKED:
                raise AdapterError("adapter_revoked", "This adapter is revoked.", status_code=409)
            row = AdapterBinding.objects.create(
                makerspace=makerspace, device=locked, target_type=target_type, machine=machine,
                target_id=str(target_id)[:64] if machine is None else "", external_ref=external_ref,
                capabilities=sorted(set(capabilities)), created_by=actor)
            bump_config(locked)
            audit.record(actor, "devices.adapter_bound", makerspace=makerspace, target=locked, meta={
                "device_id": str(locked.pk), "binding_id": str(row.pk), "target_type": target_type,
                "capabilities": row.capabilities})
    except IntegrityError as exc:
        raise AdapterError("binding_exists", "This target is already bound to this adapter.", status_code=409) from exc
    return row


def unbind(actor, binding):
    with transaction.atomic():
        makerspace = lock_tenant(binding.makerspace_id)
        locked = AdapterBinding.objects.select_for_update().select_related("device").get(pk=binding.pk)
        device = locked.device
        audit.record(actor, "devices.adapter_unbound", makerspace=makerspace, target=device, meta={
            "device_id": str(device.pk), "binding_id": str(locked.pk), "target_type": locked.target_type})
        locked.delete()
        bump_config(device)


def adapter_summary(device, visible=None):
    """``visible``: binding ids the reader's machine scope reaches (``None`` = all, decision 336i)."""
    from apps.devices.telemetry_drops import dropped_since

    profile = AdapterProfile.objects.filter(device=device).first()
    bindings = AdapterBinding.objects.filter(device=device).select_related("status", "machine")
    bindings = list(bindings if visible is None else bindings.filter(pk__in=visible))
    # Online = active, seen at least once, and no open offline edge (the scan sets ``offline_since``, a heartbeat clears it).
    online = device.status == Device.Status.ACTIVE and device.last_seen_at is not None and device.offline_since is None
    return {
        "id": str(device.pk), "name": device.name, "status": device.status, "last_seen_at": device.last_seen_at,
        "adapter_kind": profile.adapter_kind if profile else None,
        "vendor": profile.vendor if profile else "", "software_version": profile.software_version if profile else "",
        "capabilities": profile.capabilities if profile else [], "config_version": profile.config_version if profile else 0,
        "hello_at": profile.hello_at if profile else None,
        "firmware": profile.firmware if profile else "", "health": profile.health if profile else "",
        "health_at": profile.health_at if profile else None,
        "online": online, "offline_since": None if online else device.offline_since,
        "telemetry_dropped_7d": dropped_since(device.makerspace_id, 7),
        "bindings": [{**binding_payload(row), "enabled": row.enabled, "status": binding_status(row),
                      **config_view(row), "offline_cache": _cache(row)} for row in bindings]}


def _cache(binding):
    if "access.cache" not in binding.capabilities:
        return None
    from apps.devices.services_adapter_offline import status_for
    return status_for(binding)


def binding_status(binding):
    row = AdapterStatus.objects.filter(binding=binding).first()
    return None if row is None else {"state": row.state, "observed_at": row.observed_at, **row.payload}


def recent_commands_queryset(device):
    return AdapterCommand.objects.filter(device=device).select_related("created_by").order_by("-created_at")


def recent_events_queryset(device):
    return AdapterEvent.objects.filter(device=device).order_by("-received_at")


def set_config(actor, binding_id, config):
    """Replace a binding's safety config (validated by the serializer); audited, config version bumped."""
    from apps.devices.adapter_access import scoped_binding
    binding = scoped_binding(actor, binding_id)
    with transaction.atomic():
        makerspace = lock_tenant(binding.makerspace_id)
        locked = AdapterBinding.objects.select_for_update().select_related("device").get(pk=binding.pk)
        before = bool((locked.config or {}).get("auto_apply_terminal"))
        locked.config = config
        locked.save(update_fields=["config"])
        if before != bool(config.get("auto_apply_terminal")):
            audit.record(actor, "devices.adapter_auto_apply_set", makerspace=makerspace, target=locked.device, meta={
                "device_id": str(locked.device_id), "binding_id": str(locked.pk),
                "auto_apply_terminal": bool(config.get("auto_apply_terminal"))})
        bump_config(locked.device)
        audit.record(actor, "devices.adapter_config_set", makerspace=makerspace, target=locked.device, meta={
            "device_id": str(locked.device_id), "binding_id": str(locked.pk), "config": config})
    return locked

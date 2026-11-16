"""Adapter hello and bindings: the capability declaration and the targets the adapter serves."""
from django.db import transaction
from django.utils import timezone

from apps.devices.adapter_access import adapter_device
from apps.devices.adapters.hello import HELLO
from apps.devices.adapters.registry import CAPABILITIES, PROTOCOL_VERSION
from apps.devices.models import AdapterBinding, AdapterProfile
from apps.devices.services_adapter_core import audit_adapter, cache_keys, check

POLL_SECONDS = 15


def binding_payload(binding):
    return {
        "id": str(binding.pk), "target_type": binding.target_type,
        "machine_id": binding.machine_id, "target_id": binding.target_id,
        "external_ref": binding.external_ref, "capabilities": list(binding.capabilities),
    }


def bindings_for(device):
    rows = AdapterBinding.objects.filter(device=device, makerspace_id=device.makerspace_id, enabled=True)
    return [binding_payload(row) for row in rows]


def hello(principal, data):
    """Record what the adapter says it can do. Unknown capability names are reported back, never fatal."""
    check(HELLO, data, label="hello")
    declared = [row for row in data["capabilities"] if row["name"] in CAPABILITIES]
    unknown = sorted({row["name"] for row in data["capabilities"] if row["name"] not in CAPABILITIES})
    now = timezone.now()
    with transaction.atomic():
        device = adapter_device(principal, lock=True)
        profile = AdapterProfile.objects.select_for_update().filter(device=device).first()
        names = sorted(row["name"] for row in declared)
        changed = profile is None or sorted(r["name"] for r in profile.capabilities) != names \
            or profile.adapter_kind != data["adapter_kind"]
        profile, _created = AdapterProfile.objects.update_or_create(device=device, defaults={
            "makerspace_id": device.makerspace_id, "protocol_version": data["protocol_version"],
            "adapter_kind": data["adapter_kind"], "vendor": data.get("vendor", ""),
            "software_version": data.get("software_version", ""), "capabilities": declared, "hello_at": now,
            "firmware": data.get("firmware", ""), "health": data.get("health", ""), "health_at": now,
            **({"config_version": (profile.config_version + 1) if profile else 1} if changed else {})})
        if changed:
            audit_adapter(device.makerspace, device, "devices.adapter_hello",
                          meta={"adapter_kind": data["adapter_kind"], "capabilities": names})
    return {
        "device_id": str(device.pk), "protocol_version": PROTOCOL_VERSION, "server_time": int(now.timestamp()),
        "config_version": profile.config_version, "poll_seconds": POLL_SECONDS,
        "capabilities": declared, "unknown_capabilities": unknown, "bindings": bindings_for(device),
        "cache_keys": cache_keys(),
    }


def bump_config(device):
    """Staff changed what the adapter serves: its next status/hello response shows a new config_version."""
    profile = AdapterProfile.objects.select_for_update().filter(device=device).first()
    if profile is not None:
        profile.config_version += 1
        profile.save(update_fields=["config_version"])
        from apps.devices.services_adapter_webhook import wake
        wake(device, "config.changed")

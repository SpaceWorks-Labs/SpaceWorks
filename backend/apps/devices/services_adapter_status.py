"""Status reports and typed events from an adapter (idempotent, bounded, schema-validated)."""
from datetime import datetime, timedelta, timezone as dt_timezone

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.devices.adapter_access import adapter_device, declared
from apps.devices.adapters.caps import events as events_cap
from apps.devices.adapters.registry import event_schema, status_schema
from apps.devices.adapters.schema import UUID, obj
from apps.devices.adapters.schema import EPOCH
from apps.devices.adapter_event_handlers import handle
from apps.devices.models import AdapterBinding, AdapterEvent, AdapterProfile, AdapterStatus
from apps.devices import services_adapter_detect as detect
from apps.devices import services_adapter_history as history
from apps.devices.adapter_access import require_adapters, switch_for
from apps.devices.services_adapter_safety import track_idle
from apps.devices.services_offline import record_activity_locked
from apps.devices.services_adapter_core import MAX_ITEMS, AdapterError, check

MIN_INTERVAL_SECONDS = 5
MAX_FUTURE_SECONDS = 300
STATUS_BODY = obj({"items": {"type": "array", "maxItems": MAX_ITEMS, "items": {"type": "object"}}}, ["items"])
EVENT_ITEM = obj({"operation_id": UUID, "binding_id": UUID, "type": {"type": "string", "maxLength": 48},
                  "observed_at": EPOCH, "data": {"type": "object"}}, ["operation_id", "type", "observed_at", "data"])
EVENTS_BODY = obj({"events": {"type": "array", "maxItems": MAX_ITEMS, "items": {"type": "object"}}}, ["events"])


def _moment(epoch, now):
    value = datetime.fromtimestamp(epoch, tz=dt_timezone.utc)
    if value > now + timedelta(seconds=MAX_FUTURE_SECONDS):
        raise AdapterError("observed_in_future", "The observation time is in the future.")
    return value


def _config_version(device):
    profile = AdapterProfile.objects.filter(device=device).first()
    return profile.config_version if profile else 0


def store_status(principal, body):
    """One result per item: stored, stale (not newer), throttled (too soon) or unknown_binding. Never fails the batch."""
    check(STATUS_BODY, body, label="status report")
    now = timezone.now()
    results = []
    with transaction.atomic():
        device = adapter_device(principal, lock=True)
        # A status call is liveness: it clears an offline edge (and notifies the recovery) like a heartbeat does.
        record_activity_locked(device.makerspace, device, now=now)
        for item in body["items"]:
            binding = AdapterBinding.objects.filter(pk=item.get("binding_id") if _is_uuid(item) else None,
                                                    device=device, enabled=True).first()
            if binding is None:
                results.append({"binding_id": str(item.get("binding_id", "")), "result": "unknown_binding"})
                continue
            check(status_schema(binding.capabilities), item, label="status item")
            results.append({"binding_id": str(binding.pk), "result": _store_one(binding, item, now)})
    return {"results": results, "config_version": _config_version(device), "server_time": int(now.timestamp())}


def _is_uuid(item):
    from apps.devices.adapters.schema import errors
    return isinstance(item, dict) and not errors(UUID, item.get("binding_id"))


def _store_one(binding, item, now):
    observed = _moment(item["observed_at"], now)
    current = AdapterStatus.objects.select_for_update().filter(binding=binding).first()
    if current is not None and observed <= current.observed_at:
        return "stale"
    if current is not None and now - current.received_at < timedelta(seconds=MIN_INTERVAL_SECONDS):
        return "throttled"
    payload = {key: value for key, value in item.items() if key not in ("binding_id", "observed_at", "state")}
    idle_since = track_idle(current, item["state"], observed)  # server-kept: when the idle stretch began
    if idle_since is not None:
        payload["idle_since"] = idle_since
    if current is not None and "area_clear" not in payload and "area_clear" in current.payload:
        payload["area_clear"] = current.payload["area_clear"]  # the confirmation survives ordinary status reports
    AdapterStatus.objects.update_or_create(binding=binding, defaults={
        "makerspace_id": binding.makerspace_id, "state": item["state"], "payload": payload,
        "observed_at": observed, "received_at": now})
    history.record_status(binding, payload, observed)
    if isinstance(payload.get("diagnostics"), dict):
        detect.record_health(binding.device, payload["diagnostics"])
    return "stored"


def ingest_events(principal, body):
    """Append typed events; a repeated ``operation_id`` is a no-op (``duplicate``), an unknown type is refused."""
    check(EVENTS_BODY, body, label="events body")
    now = timezone.now()
    results = []
    with transaction.atomic():
        device = adapter_device(principal, lock=True)
        names = declared(device) | {events_cap.CAPABILITY.name}
        for item in body["events"]:
            check(EVENT_ITEM, item, label="event")
            capability, schema = event_schema(sorted(names), item["type"])
            if schema is None:
                raise AdapterError("event_not_declared", "This event type is not served by a declared capability.",
                                   event_type=item["type"][:48])
            check(schema, item["data"], label="event data")
            switch = switch_for(capability)
            if switch:
                require_adapters(device.makerspace_id, switch)  # a capability whose child switch is off is 404
            binding = None
            if item.get("binding_id"):
                binding = AdapterBinding.objects.filter(pk=item["binding_id"], device=device, enabled=True).first()
                if binding is None or (capability != "events" and capability not in binding.capabilities):
                    raise AdapterError("binding_unknown", "That binding does not serve this capability.",
                                       status_code=404)
            if item["type"] == "detection.reported":
                detect.admit(binding, item["data"])
            results.append({"operation_id": item["operation_id"],
                            "result": _append(device, binding, capability, item, now)})
    return {"results": results}


def _append(device, binding, capability, item, now):
    try:
        with transaction.atomic():
            row = AdapterEvent.objects.create(
                makerspace_id=device.makerspace_id, device=device, binding=binding, operation_id=item["operation_id"],
                event_type=item["type"], capability=capability, data=item["data"],
                observed_at=_moment(item["observed_at"], now), received_at=now)
    except IntegrityError:
        return "duplicate"
    handle(device, binding, row)
    if row.event_type == "sensor.reading":
        history.record_sensor(binding, row.data, row.observed_at)
    return "stored"

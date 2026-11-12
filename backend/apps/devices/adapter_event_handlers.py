"""Server-side reactions to adapter events. Every handler is fail-safe: a reaction problem never loses the event.

``maintenance.fault`` goes to the machine's existing technical-fault log (``machines.services.log_error``), the
maintenance workflow's intake. ``safety.area_cleared`` records the area-clear confirmation the job lease and
the access decision enforce. The rest (scan, sensor, door, consumable, calibration events) are stored as the
append-only ``AdapterEvent`` row and surface to staff only.
"""
import logging

from django.db import transaction

from apps.devices.models import AdapterStatus

logger = logging.getLogger(__name__)
SEVERITY = {"info": "info", "warning": "warning", "fault": "error"}


def _maintenance_fault(device, binding, event):
    if binding is None or binding.machine_id is None:
        return
    from apps.machines import services
    data = event.data
    message = f"[{data['code']}] {data.get('detail', '')}".strip()[:500]
    services.log_error(binding.machine, None, SEVERITY[data["severity"]], message)


def _area_cleared(device, binding, event):
    if binding is None:
        return
    status = AdapterStatus.objects.select_for_update().filter(binding=binding).first()
    if status is not None:
        status.payload = {**status.payload, "area_clear": bool(event.data["confirmed"])}
        status.save(update_fields=["payload"])


def _notify(device, binding, event):
    from apps.devices.adapter_notifications import on_event
    on_event(event)


HANDLERS = {"maintenance.fault": _maintenance_fault, "safety.area_cleared": _area_cleared,
            "job.needs_attention": _notify, "consumable.runout": _notify, "detection.reported": _notify}


def handle(device, binding, event):
    handler = HANDLERS.get(event.event_type)
    if handler is None:
        return
    try:
        with transaction.atomic():
            handler(device, binding, event)
    except Exception:  # noqa: BLE001 - the event row is already durable; never fail the adapter's report
        logger.warning("adapter event handler failed", extra={"event_type": event.event_type}, exc_info=True)

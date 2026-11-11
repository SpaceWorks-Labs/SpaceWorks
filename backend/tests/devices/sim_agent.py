"""A SIMULATED printer agent for tests only (release 2 L10, #76). Never shipped or packaged.

It speaks the real signed protocol v1 against the integration routes: the heartbeat with a
status snapshot, the queue pull and the job reports.
"""
import json
import time

from rest_framework.test import APIClient

from apps.devices.models import Device, MachineTypeIntegration
from tests.devices.helpers import HEARTBEAT, signed_headers

QUEUE = "/api/v1/device/integrations/queue"


def report_path(request_id):
    return f"/api/v1/device/integrations/jobs/{request_id}/report"


class SimAgent:
    def __init__(self, device, private_key):
        self.device, self.private = device, private_key
        self.client = APIClient()

    def _headers(self, target, body=b"", method="POST"):
        self.device.refresh_from_db()
        return signed_headers(self.device.pk, self.device.key_version, self.private, target=target, body=body,
                              method=method)

    def post(self, target, data):
        body = json.dumps(data, separators=(",", ":")).encode()
        return self.client.post(target, body, content_type="application/json", **self._headers(target, body))

    def heartbeat(self, snapshot=None):
        if snapshot is None:
            return self.client.post(HEARTBEAT, b"", content_type="application/json", **self._headers(HEARTBEAT))
        return self.post(HEARTBEAT, {"status_snapshot": snapshot})

    def queue(self):
        return self.client.get(QUEUE, **self._headers(QUEUE, method="GET"))

    def report(self, request_id, **data):
        return self.post(report_path(request_id), data)


def snapshot(**changes):
    return {"schema_version": 1, "observed_at": int(time.time()), "state": "printing", "progress_percent": 42,
            "layer_current": 10, "layer_total": 200, "temperatures": {"nozzle": 215.4, "bed": 60},
            "spools": [{"slot": 0, "material": "PLA", "colour": "Black", "remaining_percent": 80}],
            "clear_token": "bed-ok-1", **changes}


def enable_integrations(space):
    space.enabled_modules = sorted(set(space.enabled_modules or []) | {"devices", "machines", "machine_service"})
    space.enabled_features = sorted(set(space.enabled_features or []) | {"machines.integrations"})
    space.save(update_fields=["enabled_modules", "enabled_features"])


def integrated_case(slug, *, auto=False, enabled=True, bind_type=True):
    """An enrolled printer bound to a machine whose type has a printer agent; no requests yet."""
    from apps.devices.services_printer_bindings import create_binding
    from tests.devices.helpers import active_device
    from tests.test_machine_service_workflow import machine

    space, actor, client, device_id, private = active_device(slug)
    space.enabled_modules = sorted(set(space.enabled_modules or []) | {"machines", "machine_service"})
    space.save(update_fields=["enabled_modules"])
    if enabled:
        enable_integrations(space)
    target = machine(space)
    binding = create_binding(actor, space.pk, device_id=device_id, machine_id=target.pk, auto_apply_terminal=auto)
    if bind_type:
        MachineTypeIntegration.objects.create(makerspace=space, machine_type=target.machine_type,
                                              kind=MachineTypeIntegration.Kind.PRINTER_AGENT, enabled=True)
    device = Device.objects.get(pk=device_id)
    return {"space": space, "actor": actor, "client": client, "device": device, "machine": target,
            "binding": binding, "agent": SimAgent(device, private), "private": private}


def started_request(case):
    from tests.test_machine_service_workflow import in_progress
    return in_progress(case["space"], actor=case["actor"], target=case["machine"])


def accepted_request(case):
    from apps.machines.service_workflow_actions import accept
    from tests.test_machine_service_workflow import request
    row = request(case["space"], target=case["machine"], actor=case["actor"])
    return accept(row, case["actor"])

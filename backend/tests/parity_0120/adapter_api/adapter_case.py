"""Shared fixtures for the Device Adapter API route tests: a space with the switches on, an enrolled adapter
that speaks the real signed protocol, a bound machine, and a SIMULATED adapter client (tests only)."""
import json

from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.devices.models import Device
from tests.devices.helpers import active_device, create_device, enroll, signed_headers, staff_client
from tests.return_helpers import make_member, make_space
from tests.test_machine_service_workflow import machine

BASE = "/api/v1/device/adapter/v1/"
CHILDREN = ("machines.integrations.access", "machines.integrations.usage_billing", "machines.integrations.video",
            "machines.integrations.kiosk", "machines.integrations.recording", "machines.integrations.audio",
            "machines.integrations.talk", "machines.integrations.audio_recording", "machines.integrations.artifacts",
            "machines.integrations.detections", "machines.integrations.telemetry_history",
            "machines.integrations.diagnostics", "machines.integrations.offline_cache")


def enable(space, *, features=("machines.integrations", *CHILDREN)):
    space.enabled_modules = sorted(set(space.enabled_modules or []) | {"devices", "machines", "machine_service"})
    space.enabled_features = sorted(set(space.enabled_features or []) | set(features))
    space.save(update_fields=["enabled_modules", "enabled_features"])


class SimAdapter:
    """Signs every request like a real adapter would (see docs/device-adapters/authentication.md)."""

    def __init__(self, device, private_key):
        self.device, self.private = device, private_key
        self.client = APIClient()

    def _headers(self, target, body=b"", method="POST", **kwargs):
        self.device.refresh_from_db()
        return signed_headers(self.device.pk, self.device.key_version, self.private, target=target, body=body,
                              method=method, **kwargs)

    def post(self, path, data=None, **kwargs):
        target = BASE + path
        body = json.dumps(data if data is not None else {}, separators=(",", ":")).encode()
        return self.client.post(target, body, content_type="application/json", **self._headers(target, body, **kwargs))

    def get(self, path):
        target = BASE + path
        return self.client.get(target, **self._headers(target, method="GET"))

    def hello(self, capabilities, kind="fdm_printer"):
        return self.post("hello", {"protocol_version": 1, "adapter_kind": kind,
                                   "capabilities": [{"name": name, "version": 1} for name in capabilities]})


def adapter_case(slug, *, features=("machines.integrations", *CHILDREN), caps=("status", "events", "control",
                                                                               "access.authorize", "usage.log",
                                                                               "maintenance.report", "safety"),
                 extra=()):
    """A dict with the space, staff client, SimAdapter, machine and binding id: the adapter has said hello (``caps`` plus
    ``extra`` declared) and ``caps`` (minus status) are bound to one machine."""
    space = make_space(slug)
    enable(space, features=features)
    manager, client = staff_client(space, f"{slug}-manager")
    created = client.post(reverse("devices:admin-device-list", args=[space.pk]),
                          {"kind": "adapter", "name": "Bridge 1"}, format="json")
    assert created.status_code == 201, created.data
    response, private, _public = enroll(created.data["enrollment"])
    assert response.status_code == 200, response.data
    device = Device.objects.get(pk=created.data["device"]["id"])
    sim = SimAdapter(device, private)
    assert sim.hello([*caps, *extra]).status_code == 200
    target = machine(space)
    bound = client.post(reverse("devices:admin-adapter-binding-create", args=[device.pk]),
                        {"target_type": "machine", "machine_id": target.pk, "capabilities": list(caps[1:])},
                        format="json")
    assert bound.status_code == 201, bound.data
    return {"space": space, "manager": manager, "client": client, "sim": sim, "machine": target,
            "binding_id": bound.data["id"], "device": device}


def plain_member(slug, space):
    return make_member(slug, space, membership_role="member", role=User.Role.REQUESTER)


__all__ = ["active_device", "create_device", "adapter_case", "plain_member", "SimAdapter", "enable"]

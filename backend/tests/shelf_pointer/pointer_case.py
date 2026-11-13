"""Shared fixture for the shelf-pointer tests: a space with the integrations switch on, one pointer bound to the
whole space (locate.calibrate + locate.indicate), a few products with storage locations and a SimShelfPointer that
speaks the real signed protocol through the Django test client."""
import json

from django.urls import reverse
from rest_framework.test import APIClient

from apps.inventory.models import InventoryProduct
from tests.adapter_conformance.client import AdapterClient
from tests.adapter_conformance.sim_shelf_pointer import SimShelfPointer
from tests.parity_0120.adapter_api.adapter_case import adapter_case

PAN_TILT = {"kind": "pan_tilt", "pan_deg": 12.5, "tilt_deg": -3, "laser_power_pct": 80}


class DjangoTransport:
    def __init__(self):
        self.client = APIClient()

    def send(self, method, path, body, headers):
        meta = {"REQUEST_URI": path, **{"HTTP_" + k.upper().replace("-", "_"): v for k, v in headers.items()}}
        if method == "POST":
            response = self.client.post(path, body, content_type="application/json", **meta)
        else:
            response = self.client.get(path, **meta)
        return response.status_code, (json.loads(response.content) if response.content else None)


def pointer_case(slug, **kwargs):
    case = adapter_case(slug, caps=("status", "events"), extra=("locate.calibrate", "locate.indicate"), **kwargs)
    shelf = case["client"].post(reverse("devices:admin-adapter-binding-create", args=[case["device"].pk]), {
        "target_type": "space", "external_ref": "shelf-wall", "capabilities": ["locate.calibrate", "locate.indicate"]},
        format="json")
    assert shelf.status_code == 201, shelf.data
    case["pointer_binding"] = shelf.data["id"]
    case["products"] = {name: InventoryProduct.objects.create(makerspace=case["space"], name=name, storage_location=loc)
                        for name, loc in (("Resistors", "Shelf A"), ("Bolts", "Shelf B"), ("Nuts", "Shelf B"))}
    device = case["device"]
    client = AdapterClient(DjangoTransport(), device.pk, device.key_version, case["sim"].private)
    case["pointer"] = SimShelfPointer(client, case["pointer_binding"])
    return case


def save_pose(case, target_id, pose=PAN_TILT, target_type="storage_location"):
    return case["client"].put(reverse("devices:admin-adapter-poses", args=[case["pointer_binding"]]),
                              {"target_type": target_type, "target_id": target_id, "pose": pose}, format="json")


def set_caps(case, **config):
    return case["client"].put(reverse("devices:admin-adapter-binding-config", args=[case["pointer_binding"]]),
                              config, format="json")

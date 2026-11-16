"""Signed-device-only switches use Ed25519 requests, never invented JWT routes."""
import time
from uuid import uuid4

import pytest
from tests.modules.test_switch_matrix_objects_rest_isolation import cx11b_isolated_phase  # noqa: F401

from apps.devices.models import AdapterAccessLog, AdapterBinding, AdapterUsageLog
from tests.inventory.switch_support_cx11b_p1 import prove_route
from tests.parity_0120.adapter_api.adapter_case import adapter_case
from tests.parity_0120.adapter_api.test_kiosk_checkout import kiosk, start

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.area_machines, pytest.mark.area_devices]
KINDS = ("access", "usage_billing", "offline_cache", "kiosk")
CASES = [(kind, key) for kind in KINDS for key in (
    f"machines.integrations.{kind}", "machines.integrations", "devices", "machines", "machine_service")]


@pytest.mark.parametrize("kind,key", CASES)
def test_signed_adapter_child_switch_is_inert_off_and_resumes_the_same_binding(kind, key):
    if kind == "kiosk":
        case = kiosk("p1-signed-kiosk")
        binding = AdapterBinding.objects.get(pk=case["kiosk_binding"])
        call = lambda _: start(case)
        on = (201, None)
    else:
        caps = ("status", "events", "access.authorize", "access.cache", "usage.log")
        case = adapter_case("p1-signed", caps=caps)
        binding = AdapterBinding.objects.get(pk=case["binding_id"])
        if kind == "access":
            # A normal unknown credential has a recorded denial, not a switch refusal.
            call = lambda _: case["sim"].post("access/authorize", {
                "binding_id": str(binding.pk), "credential": {"type": "nfc", "value": "DEADBEEF"}})
        elif kind == "usage_billing":
            now = int(time.time())
            body = {"binding_id": str(binding.pk), "operation_id": str(uuid4()), "started_at": now - 600,
                    "ended_at": now, "active_minutes": 8, "idle_minutes": 2, "outcome": "completed"}
            call = lambda _: case["sim"].post("usage", body)
        else:
            call = lambda _: case["sim"].get(f"access/cache?binding_id={binding.pk}")
        on = (200, None)
    objects = {"binding": binding, "device": case["device"], "machine": case["machine"]}
    prove_route(case["space"], case["sim"], objects, key, call, off=(404, "module_disabled" if key == "devices" else "not_found"),
                named_switch=False, on=on)
    if kind == "usage_billing":
        assert AdapterUsageLog.objects.filter(binding=binding, operation_id=body["operation_id"]).count() == 1
    if kind == "access":
        assert AdapterAccessLog.objects.filter(binding=binding, allowed=False, reason="unknown_credential").count() == 1

pytestmark = ([pytestmark] if not isinstance(pytestmark, list) else pytestmark) + [
    pytest.mark.usefixtures("cx11b_isolated_phase")]

"""Device Adapter API v1: signed auth, replay, revocation, switch-off 404, capability gating, cross-tenant 404."""
import uuid

import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from apps.devices.models import AdapterProfile, Device
from tests.parity_0120.adapter_api.adapter_case import BASE, SimAdapter, adapter_case, enable
from tests.return_helpers import make_space
from tests.devices.helpers import signed_headers

pytestmark = pytest.mark.django_db(transaction=True)


def test_hello_declares_capabilities_and_lists_bindings():
    case = adapter_case("ad-hello")
    response = case["sim"].hello(["status", "events", "control", "bogus.cap"])
    assert response.status_code == 200, response.data
    assert response.data["unknown_capabilities"] == ["bogus.cap"]
    assert {row["name"] for row in response.data["capabilities"]} == {"status", "events", "control"}
    assert AdapterProfile.objects.get(device=case["device"]).adapter_kind == "fdm_printer"
    assert case["sim"].get("bindings").data["bindings"][0]["id"] == case["binding_id"]


def test_invalid_hello_is_a_typed_400():
    case = adapter_case("ad-badhello")
    response = case["sim"].post("hello", {"protocol_version": 1, "adapter_kind": "toaster", "capabilities": []})
    assert response.status_code == 400 and response.data["code"] == "invalid_payload"


def test_a_replayed_nonce_is_refused():
    case = adapter_case("ad-replay")
    sim = case["sim"]
    headers = sim._headers(BASE + "status", b"{}", nonce="AAAAAAAAAAAAAAAAAAAAAA")
    first = sim.client.post(BASE + "status", b"{}", content_type="application/json", **headers)
    second = sim.client.post(BASE + "status", b"{}", content_type="application/json", **headers)
    assert first.status_code in (200, 400) and second.status_code == 401


def test_unsigned_and_wrong_kind_devices_are_refused():
    case = adapter_case("ad-kind")
    assert APIClient().post(BASE + "hello", {}, format="json").status_code in (401, 403)
    space = case["space"]
    from tests.devices.helpers import create_device, enroll
    created = create_device(case["client"], space, kind="printer")
    _response, private, _public = enroll(created["enrollment"])
    printer = Device.objects.get(pk=created["device"]["id"])
    assert SimAdapter(printer, private).hello(["status"]).status_code == 403  # not an adapter kind route


def test_a_revoked_adapter_is_refused_everywhere():
    case = adapter_case("ad-revoked")
    revoke = case["client"].post(reverse("devices:admin-device-revoke", args=[case["device"].pk]))
    assert revoke.status_code == 200
    assert case["sim"].get("bindings").status_code in (401, 403)
    assert case["sim"].post("status", {"items": []}).status_code in (401, 403)


def test_every_route_is_404_while_the_switch_is_off():
    case = adapter_case("ad-off")
    space = case["space"]
    space.enabled_features = [key for key in space.enabled_features if not key.startswith("machines.integrations")]
    space.save(update_fields=["enabled_features"])
    sim = case["sim"]
    assert sim.post("hello", {"protocol_version": 1, "adapter_kind": "generic", "capabilities": []}).status_code == 404
    assert sim.get("bindings").status_code == 404
    assert sim.post("status", {"items": []}).status_code == 404
    assert sim.post("commands/lease").status_code == 404
    assert case["client"].get(reverse("devices:admin-adapter-list", args=[space.pk])).status_code == 404
    refused = case["client"].post(reverse("devices:admin-device-list", args=[space.pk]),
                                  {"kind": "adapter", "name": "x"}, format="json")
    assert refused.status_code == 404


def test_a_child_switch_off_hides_only_its_routes():
    case = adapter_case("ad-child", features=("machines.integrations",))
    body = {"binding_id": case["binding_id"], "credential": {"type": "nfc", "value": "04A1B2C3"}}
    assert case["sim"].post("access/authorize", body).status_code == 404
    assert case["sim"].post("status", {"items": []}).status_code == 200


def test_an_event_from_an_undeclared_capability_is_refused():
    case = adapter_case("ad-undeclared", caps=("status", "events", "control"))
    event = {"operation_id": str(uuid.uuid4()), "type": "sensor.reading", "observed_at": 1_700_000_000,
             "data": {"sensor": "t", "value": 1}}
    response = case["sim"].post("events", {"events": [event]})
    assert response.status_code == 400 and response.data["code"] == "event_not_declared"


def test_staff_cannot_see_another_tenants_adapter():
    mine, other = adapter_case("ad-tenant-a"), adapter_case("ad-tenant-b")
    for name in ("admin-adapter-detail", "admin-adapter-commands", "admin-adapter-events"):
        assert mine["client"].get(reverse(f"devices:{name}", args=[other["device"].pk])).status_code == 404
    assert mine["client"].get(reverse("devices:admin-adapter-binding-detail", args=[other["binding_id"]])).status_code == 404


def test_a_member_without_manage_devices_is_refused():
    from tests.parity_0120.adapter_api.adapter_case import plain_member
    case = adapter_case("ad-rbac")
    member = plain_member("ad-rbac-member", case["space"])
    client = APIClient()
    client.force_authenticate(member)
    assert client.get(reverse("devices:admin-adapter-list", args=[case["space"].pk])).status_code in (403, 404)
    assert client.get(reverse("devices:admin-adapter-poses", args=[case["binding_id"]])).status_code in (403, 404)


def test_the_adapter_cannot_call_admin_routes():
    case = adapter_case("ad-noadmin")
    target = reverse("devices:admin-adapter-list", args=[case["space"].pk])
    headers = signed_headers(case["device"].pk, case["device"].key_version, case["sim"].private, target=target,
                             method="GET")
    assert APIClient().get(target, **headers).status_code in (401, 403)


def test_the_adapter_limit_key_refuses_a_new_bridge():
    case = adapter_case("ad-limit")
    space = case["space"]
    space.resource_limit_overrides = {"adapter_bridges": 1}
    space.save(update_fields=["resource_limit_overrides"])
    response = case["client"].post(reverse("devices:admin-device-list", args=[space.pk]),
                                   {"kind": "adapter", "name": "Bridge 2"}, format="json")
    assert response.status_code == 409 and response.data["code"] == "adapter_bridges_quota_reached"


def test_enable_helper_is_idempotent():
    space = make_space("ad-enable")
    enable(space)
    enable(space)
    assert space.enabled_features.count("machines.integrations") == 1

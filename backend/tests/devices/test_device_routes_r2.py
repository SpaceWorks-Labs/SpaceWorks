"""The integration routes are registered device routes: signed, printer-only, default-deny."""
import pytest

from apps.devices import route_registry
from apps.devices.checks import discover_device_routes, registry_errors
from tests.devices.helpers import active_device, signed_headers
from tests.devices.sim_agent import QUEUE, enable_integrations

pytestmark = pytest.mark.django_db(transaction=True)


def test_the_two_integration_routes_are_signed_printer_routes_with_no_module_shortcut():
    for key in (("devices:device-integration-queue", "GET"), ("devices:device-integration-job-report", "POST")):
        entry = route_registry.DEVICE_ROUTES[key]
        assert entry.auth_mode == route_registry.DEVICE_SIGNATURE
        assert entry.kinds == frozenset({"printer"}) and entry.modules == ()
    assert registry_errors(discover_device_routes()) == []


def test_unsigned_and_non_printer_callers_are_refused():
    from rest_framework.test import APIClient
    assert APIClient().get(QUEUE).status_code in (401, 403)
    space, _actor, client, _device_id, _private = active_device("int-label-kind")
    created = client.post(f"/api/v1/admin/makerspace/{space.pk}/devices", {"kind": "label_printer", "name": "Labels"},
                          format="json").data
    from tests.devices.helpers import enroll
    _response, private, _public = enroll(created["enrollment"])
    enable_integrations(space)
    headers = signed_headers(created["device"]["id"], 1, private, target=QUEUE, method="GET")
    assert APIClient().get(QUEUE, **headers).status_code == 403

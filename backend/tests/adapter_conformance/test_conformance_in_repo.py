"""The conformance kit against this repo's own server, through the Django test client (the CLI uses a URL)."""
import json

import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from tests.adapter_conformance.client import AdapterClient
from tests.adapter_conformance.conformance import report, run
from tests.parity_0120.adapter_api.adapter_case import adapter_case

pytestmark = pytest.mark.django_db(transaction=True)


class DjangoTransport:
    def __init__(self):
        self.client = APIClient()

    def send(self, method, path, body, headers):
        meta = {"REQUEST_URI": path, **{"HTTP_" + key.upper().replace("-", "_"): value for key, value in headers.items()}}
        if method == "POST":
            response = self.client.post(path, body, content_type="application/json", **meta)
        elif method == "DELETE":
            response = self.client.delete(path, **meta)
        else:
            response = self.client.get(path, **meta)
        return response.status_code, (json.loads(response.content) if response.content else None)


def test_the_mock_adapter_passes_every_conformance_check():
    case = adapter_case("conf-run")
    queued = case["client"].post(reverse("devices:admin-adapter-binding-command", args=[case["binding_id"]]),
                                 {"capability": "control", "command": "pause", "params": {}}, format="json")
    assert queued.status_code == 201
    device = case["device"]
    client = AdapterClient(DjangoTransport(), device.pk, device.key_version, case["sim"].private)
    results = run(client, case["binding_id"], expect_command=True)
    assert report(results), [row for row in results if not row[1]]


def test_the_media_and_data_checks_pass_in_repo():
    """``run_media`` was only reachable from the URL runner; run it here too (the cache check skips on a 404)."""
    from tests.adapter_conformance.conformance import run_media
    from tests.adapter_conformance.mock_adapter import MockAdapter
    case = adapter_case("conf-media")
    device = case["device"]
    client = AdapterClient(DjangoTransport(), device.pk, device.key_version, case["sim"].private)
    status, hello = MockAdapter(client, case["binding_id"]).hello()
    assert status == 200, hello
    results = run_media(client, case["binding_id"], hello["cache_keys"])
    assert report(results), [row for row in results if not row[1]]


def test_the_server_holds_every_contract_rail():
    """NCA-AUDIT-2: unsigned/tampered requests, strict bodies, foreign ids and typed refusals on every route family."""
    from tests.adapter_conformance.rails import run_rails
    case = adapter_case("conf-rails")
    device = case["device"]
    client = AdapterClient(DjangoTransport(), device.pk, device.key_version, case["sim"].private)
    results = run_rails(client, case["binding_id"])
    assert report(results), [row for row in results if not row[1]]

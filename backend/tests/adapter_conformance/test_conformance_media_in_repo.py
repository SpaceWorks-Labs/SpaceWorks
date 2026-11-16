"""The conformance kit's media/data checks (decision 321) against this repo's own server.

``run_media`` was shipped in the kit but never executed in-repo; this runs it with every child switch on and a
binding that serves the media and data capabilities, so the published kit cannot drift from the server.
"""
import pytest
from django.core.cache import cache

from tests.adapter_conformance.client import AdapterClient
from tests.adapter_conformance.conformance import report, run_media
from tests.adapter_conformance.mock_adapter import MockAdapter
from tests.adapter_conformance.test_conformance_in_repo import DjangoTransport
from tests.parity_0120.adapter_api.adapter_case import adapter_case

pytestmark = pytest.mark.django_db(transaction=True)
MEDIA = ("status", "events", "access.authorize", "access.cache", "artifact.upload", "detection.report")


@pytest.fixture(autouse=True)
def _clear():
    cache.clear()


def test_the_mock_adapter_passes_every_media_conformance_check():
    case = adapter_case("conf-media", caps=MEDIA)
    device = case["device"]
    client = AdapterClient(DjangoTransport(), device.pk, device.key_version, case["sim"].private)
    status, hello = MockAdapter(client, case["binding_id"]).hello()
    assert status == 200 and hello["cache_keys"], hello
    results = run_media(client, case["binding_id"], hello["cache_keys"])
    names = {name for name, _ok, _detail in results}
    assert "the offline access cache is Ed25519-signed, names its kid and expires" in names
    assert report(results), [row for row in results if not row[1]]

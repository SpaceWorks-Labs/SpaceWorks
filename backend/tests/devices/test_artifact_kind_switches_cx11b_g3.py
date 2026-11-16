"""Sensitive artifact kinds have independent diagnostics/audio-recording read gates."""
import pytest
from tests.modules.test_switch_matrix_objects_rest_isolation import cx11b_isolated_phase  # noqa: F401

from tests.devices.route_world_cx11b_g3 import artifact, world
from tests.maintenance.route_support_cx11b_g3 import foreign_refusal, prove, send

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.area_devices, pytest.mark.area_machines]
CASES = [(kind, key, url_route, native) for kind, keys in (
    ("log_bundle", ("machines.integrations.diagnostics",)),
    ("audio_recording", ("machines.integrations.audio_recording", "machines.integrations.audio")))
    for key in keys for url_route in (False, True) for native in (False, True)]


@pytest.mark.parametrize("kind,key,url_route,native", CASES)
def test_sensitive_artifact_kind_is_hidden_off_and_same_bytes_return_on(kind, key, url_route, native, monkeypatch):
    w = world(native)
    row = artifact(w, kind)
    signed = "https://storage.example.test/retained-sensitive"
    monkeypatch.setattr("apps.machines.service_storage.presigned_download_url", lambda *a: signed)
    name, args = ("admin-adapter-artifact-url", [row.pk]) if url_route else ("admin-adapter-artifacts", [w.binding.pk])

    def check(response):
        if url_route:
            assert response.data == {"url": signed, "kind": kind, "content_type": row.content_type}
        else:
            assert [(r["id"], r["kind"]) for r in response.data["results"]] == [(str(row.pk), kind)]

    def hidden(response):
        assert response.data["count"] == 0 and response.data["results"] == []

    prove(w.space, {**w.objects, "artifact": row}, key,
          lambda c: send(c or w.client, "devices:" + name, args), check,
          off=(404, "not_found") if url_route else (200, None), off_check=None if url_route else hidden,
          outsiders=[(w.foreign, foreign_refusal(native))],
          audits={"devices.adapter_artifact_viewed": 1} if url_route else {})

pytestmark = ([pytestmark] if not isinstance(pytestmark, list) else pytestmark) + [
    pytest.mark.usefixtures("cx11b_isolated_phase")]

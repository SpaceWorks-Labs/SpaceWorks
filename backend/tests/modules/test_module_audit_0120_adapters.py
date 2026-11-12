"""Module audit 0.12.0: the Device Adapter API's outbound webhook obeys the space's switch.

A delivery queued while `machines.integrations` was on must not reach the outside world once
the space switches it off; the row waits (it is not killed), so switching back on resumes it.
The beat sweeps are mapped in `operations/cloud_jobs/task_sources.py`.
"""

import pytest
from django.urls import reverse

from apps.devices import services_adapter_webhook as push
from apps.devices.models import AdapterWebhookDelivery
from apps.operations.cloud_jobs.task_sources import TASK_SOURCES
from tests.parity_0120.adapter_api.adapter_case import adapter_case

pytestmark = pytest.mark.django_db(transaction=True)
URL = "https://hooks.example.com/spaceworks"


@pytest.fixture(autouse=True)
def offline_push(monkeypatch):
    # The push URL check moved to the shared outbound policy (security review M1).
    monkeypatch.setattr("apps.outbound_policy.is_public_https", lambda url, ports=None: url.startswith("https://"))
    monkeypatch.setattr("apps.devices.tasks.deliver_adapter_webhook_task.delay", lambda *a, **k: None)


def _queued(slug):
    case = adapter_case(slug)
    case["client"].put(reverse("devices:admin-adapter-webhook", args=[case["device"].pk]), {"url": URL}, format="json")
    case["client"].post(reverse("devices:admin-adapter-binding-command", args=[case["binding_id"]]),
                        {"capability": "control", "command": "pause", "params": {}}, format="json")
    return case, AdapterWebhookDelivery.objects.get(makerspace=case["space"])


def _switch(space, on):
    features = set(space.enabled_features)
    (features.add if on else features.discard)("machines.integrations")
    space.enabled_features = sorted(features)
    space.save(update_fields=["enabled_features"])


def test_a_switched_off_space_sends_no_webhook_and_resumes_when_back_on():
    case, row = _queued("audit-hook-off")
    sent = []
    _switch(case["space"], on=False)

    assert push.deliver(row.pk, post=lambda *args: sent.append(args) or 204) == "skipped"
    assert push.sweep()["attempted"] == 0
    row.refresh_from_db()
    assert sent == [] and row.status == AdapterWebhookDelivery.Status.PENDING

    _switch(case["space"], on=True)
    assert push.deliver(row.pk, post=lambda *args: sent.append(args) or 204) == "delivered"
    assert len(sent) == 1


def test_every_adapter_beat_task_is_mapped_to_its_switch_or_to_retention():
    for name in ("adapter_safety_sweep_task", "adapter_webhook_sweep_task"):
        entry = TASK_SOURCES[f"apps.devices.tasks.{name}"]
        assert entry.kind == "gated" and set(entry.source) == {"devices", "machines.integrations"}, name
    for name in ("adapter_media_sweep_task", "purge_adapter_recordings_task"):
        assert TASK_SOURCES[f"apps.devices.tasks.{name}"].kind == "platform", name

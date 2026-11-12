"""NCA audit 0.12.0 (decisions 330, 332): the 0.12.0 Celery tasks are gated per tenant, time-limited and lease-safe.

* Every task is declared to the source gate (the seven 0.12.0 tasks were not, so the coverage guards failed and the
  tasks ran under the deployment-wide unscoped writer lock).
* The outbound tasks carry per-task soft/hard limits (332a) and a killed push is only retried after its lease.
* The adapter webhook POST runs outside the claim transaction under a lease, so a duplicate attempt skips it.
* Adapter retention and pushes run one tenant boundary per space, and still run in a read-only space.
"""
from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.devices import services_adapter_webhook as push
from apps.devices.models import AdapterWebhookDelivery
from apps.tenant_migration import gate_policy
from apps.tenant_migration.source_gate_fanout_guards import validate_fanout_gate_coverage
from apps.tenant_migration.source_gate_guards import validate_task_coverage
from tests.parity_0120.adapter_api.adapter_case import adapter_case

URL = "https://hooks.example.com/spaceworks"
DEVICE_TASKS = "apps.devices.tasks."


def test_every_celery_task_and_tenant_fanout_is_declared_to_the_source_gate():
    validate_task_coverage()
    validate_fanout_gate_coverage(error_class=AssertionError)


def test_the_0120_tasks_take_the_right_boundary():
    assert gate_policy.TASK_TENANT_RESOLVERS[DEVICE_TASKS + "deliver_adapter_webhook_task"] == (
        "devices.AdapterWebhookDelivery", 0, "makerspace_id")
    assert gate_policy.TASK_TENANT_RESOLVERS["apps.integrations.tasks_transient.deliver_transient_email_task"] == (
        "integrations.EmailLog", 0, "makerspace_id")
    assert "apps.integrations.tasks_transient.deliver_transient_sms_task" in gate_policy.TASK_EXEMPTIONS
    for name in ("adapter_safety_sweep_task", "adapter_webhook_sweep_task", "adapter_media_sweep_task",
                 "purge_adapter_recordings_task"):
        assert DEVICE_TASKS + name in gate_policy.TASK_INTERNAL_PARTICIPANTS, name
    for target in ("apps.devices.services_adapter_safety.sweep_safety", "apps.devices.services_adapter_webhook.sweep",
                   "apps.devices.services_adapter_retention.sweep_media",
                   "apps.devices.services_adapter_retention.sweep_recordings",
                   "apps.card_designs.photo_batch_apply.expire_stalled"):
        assert target in gate_policy.FANOUT_GATE_PARTICIPANTS, target


def test_adapter_delivery_retention_and_safety_still_run_in_a_read_only_space():
    from apps.space_controls.write_policy import READ_ONLY_OPERATIONS
    assert {"devices.adapter_webhook", "devices.adapter_retention", "devices.adapter_safety",
            "card_photo_batch_expiry"} <= READ_ONLY_OPERATIONS


def test_outbound_tasks_have_soft_and_hard_time_limits():
    from apps.card_designs.tasks import process_photo_cutout
    from apps.devices.tasks import adapter_webhook_sweep_task, deliver_adapter_webhook_task
    from apps.presence.tasks_anthias import sync_anthias_player_task
    for task in (deliver_adapter_webhook_task, adapter_webhook_sweep_task, sync_anthias_player_task,
                 process_photo_cutout):
        assert task.soft_time_limit and task.time_limit and task.soft_time_limit < task.time_limit, task.name
    # A push killed at its hard limit is retried only after its lease has run out, never while it may be in flight.
    assert deliver_adapter_webhook_task.time_limit < push.LEASE_SECONDS
    assert push.SWEEP_BATCH * push.TIMEOUT_SECONDS < adapter_webhook_sweep_task.soft_time_limit


@pytest.fixture
def queued(monkeypatch):
    # The push URL check moved to the shared outbound policy (security review M1).
    monkeypatch.setattr("apps.outbound_policy.is_public_https", lambda url, ports=None: url.startswith("https://"))
    monkeypatch.setattr("apps.devices.tasks.deliver_adapter_webhook_task.delay", lambda *a, **k: None)
    case = adapter_case("nca-push")
    case["client"].put(reverse("devices:admin-adapter-webhook", args=[case["device"].pk]), {"url": URL}, format="json")
    case["client"].post(reverse("devices:admin-adapter-binding-command", args=[case["binding_id"]]),
                        {"capability": "control", "command": "pause", "params": {}}, format="json")
    return case, AdapterWebhookDelivery.objects.get(makerspace=case["space"])


@pytest.mark.django_db(transaction=True)
def test_a_push_is_sent_under_a_lease_so_a_duplicate_attempt_skips_it(queued):
    _case, row = queued
    now = timezone.now()
    seen = {}

    def post(url, body, headers):
        leased = AdapterWebhookDelivery.objects.get(pk=row.pk)
        seen["lease"] = leased.next_attempt_at
        seen["duplicate"] = push.deliver(row.pk, now=now)  # a second worker during the POST
        return 204

    assert push.deliver(row.pk, now=now, post=post) == "delivered"
    assert seen["lease"] == now + timedelta(seconds=push.LEASE_SECONDS)
    assert seen["duplicate"] == "skipped"
    row.refresh_from_db()
    assert row.status == "delivered" and row.attempts == 1


@pytest.mark.django_db(transaction=True)
def test_a_network_failure_after_the_claim_backs_off_and_the_sweep_prunes_per_space(queued):
    case, row = queued
    now = timezone.now()

    def fail(*_args):
        raise OSError("connection reset")

    assert push.deliver(row.pk, now=now, post=fail) == "failed"
    row.refresh_from_db()
    assert row.status == "pending" and row.last_error == "delivery_failed" and row.attempts == 1
    assert row.next_attempt_at == now + timedelta(seconds=push.BACKOFF_SECONDS[0])
    AdapterWebhookDelivery.objects.filter(pk=row.pk).update(
        status="dead", created_at=now - timedelta(days=push.RETENTION_DAYS + 1))
    result = push.sweep(now=now)
    assert result["pruned"] == 1 and result["attempted"] == 0 and result["skipped_spaces"] == 0
    assert not AdapterWebhookDelivery.objects.filter(makerspace=case["space"]).exists()


@pytest.mark.django_db(transaction=True)
def test_recording_retention_runs_per_space(monkeypatch):
    from apps.devices.models import AdapterWatch
    from apps.devices.services_adapter_retention import sweep_recordings
    from tests.parity_0120.adapter_api.test_media_label_notify import watching
    monkeypatch.setattr("apps.devices.services_adapter_recording._presign",
                        lambda key, ct: {"url": "https://s.test/u", "fields": {}})
    deleted = []
    monkeypatch.setattr("apps.machines.service_storage.purge_object", deleted.append)
    case, _plain = watching("nca-record")
    recorded = case["client"].post(reverse("devices:admin-adapter-watch-create", args=[case["binding_id"]]),
                                   {"record": True}, format="json")
    assert case["sim"].post(f"media/{recorded.data['id']}/recording", {"content_type": "video/webm"}).status_code == 201
    assert sweep_recordings(now=timezone.now() + timedelta(days=8)) == {"purged": 1, "skipped": 0}
    watch = AdapterWatch.objects.get(pk=recorded.data["id"])
    assert watch.recording_purged_at is not None
    # The presign wrote the bytes to the staging key; retention must delete that one too, not only the final key.
    from apps.machines.service_storage import staging_key
    assert set(deleted) == {watch.recording_key, staging_key(watch.recording_key)}
    assert sweep_recordings(now=timezone.now() + timedelta(days=8)) == {"purged": 0, "skipped": 0}
    bad = case["sim"].post(f"media/{recorded.data['id']}/recording", {"content_type": "text/html"})
    assert bad.status_code == 400 and bad.data["code"] == "content_type_not_allowed"


@pytest.mark.django_db(transaction=True)
def test_media_retention_runs_per_space_and_is_idempotent():
    from apps.devices.services_adapter_retention import sweep_media
    assert sweep_media() == {"telemetry": 0, "artifacts": 0, "skipped": 0}

"""Webhook push, type-profile defaults, per-binding auto-apply, max-session enforcement, kiosk shelf light, catalogue."""
import hashlib
import hmac
import json
import time
import uuid
from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.devices import services_adapter_webhook as push
from apps.devices.models import (AdapterBinding, AdapterCommand, AdapterPose, AdapterWebhook, AdapterWebhookDelivery,
                                 PrinterJob)
from tests.parity_0120.adapter_api.adapter_case import adapter_case, plain_member
from tests.parity_0120.adapter_api.test_job_dispatch import CAPS, dispatched, lease_and_ack, report
from tests.test_machine_service_workflow import in_progress

pytestmark = pytest.mark.django_db(transaction=True)
URL = "https://hooks.example.com/spaceworks"


@pytest.fixture(autouse=True)
def offline_push(monkeypatch):
    # The push URL check moved to the shared outbound policy (security review M1).
    monkeypatch.setattr("apps.outbound_policy.is_public_https", lambda url, ports=None: url.startswith("https://"))
    monkeypatch.setattr("apps.devices.tasks.deliver_adapter_webhook_task.delay", lambda *a, **k: None)


def hook_url(case, suffix=""):
    return reverse("devices:admin-adapter-webhook", args=[case["device"].pk]) + suffix


def test_sim_adapter_get_signs_the_query_string():
    case = adapter_case("push-sim-get")
    assert case["sim"].get("bindings?x=1&a=2").status_code == 200  # the signed target includes the query


# --- webhook push -------------------------------------------------------------------------------------------------
def test_the_secret_is_shown_once_rotation_changes_it_and_a_private_url_is_refused():
    case = adapter_case("push-secret")
    created = case["client"].put(hook_url(case), {"url": URL}, format="json")
    assert created.status_code == 200 and created.data["secret"].startswith("whsec_")
    assert "secret" not in case["client"].get(hook_url(case)).data
    assert "secret" not in case["client"].put(hook_url(case), {"url": URL}, format="json").data
    rotated = case["client"].post(hook_url(case, "/rotate"), format="json")
    assert rotated.data["secret"] != created.data["secret"] and rotated.data["secret_version"] == 2
    refused = case["client"].put(hook_url(case), {"url": "http://10.0.0.1/x"}, format="json")
    assert refused.status_code == 400 and refused.data["code"] == "webhook_url_refused"
    assert AuditLog.objects.filter(action__in=["devices.adapter_webhook_set", "devices.adapter_webhook_rotated"]).count() >= 3


def test_a_command_wakes_the_adapter_with_a_signed_content_free_envelope():
    case = adapter_case("push-wake")
    secret = case["client"].put(hook_url(case), {"url": URL}, format="json").data["secret"]
    case["client"].post(reverse("devices:admin-adapter-binding-command", args=[case["binding_id"]]),
                        {"capability": "control", "command": "pause", "params": {}}, format="json")
    row = AdapterWebhookDelivery.objects.get()
    assert row.event_type == "command.queued" and "data" not in row.envelope  # content-free by default
    seen = {}
    assert push.deliver(row.pk, post=lambda url, body, headers: seen.update(url=url, body=body, headers=headers) or 204) \
        == "delivered"
    stamp, digest = [part.split("=")[1] for part in seen["headers"]["X-SpaceWorks-Signature"].split(",")]
    expected = hmac.new(secret.encode(), f"{stamp}.".encode() + seen["body"], hashlib.sha256).hexdigest()
    assert hmac.compare_digest(digest, expected)
    assert json.loads(seen["body"])["type"] == "command.queued" and "pause" not in seen["body"].decode()
    row.refresh_from_db()
    assert row.status == "delivered" and row.attempts == 1


def test_failures_back_off_give_up_and_auto_disable_the_endpoint():
    case = adapter_case("push-fail")
    case["client"].put(hook_url(case), {"url": URL}, format="json")
    now = timezone.now()
    for _ in range(push.DISABLE_AFTER):
        row = push.wake(case["device"], "ping")
        assert push.deliver(row.pk, now=now + timedelta(seconds=1), post=lambda *a: 500) in ("failed", "skipped")
    hook = AdapterWebhook.objects.get(device=case["device"])
    assert hook.enabled is False and hook.disabled_reason == "too_many_failures"
    assert push.wake(case["device"], "ping") is None  # disabled: nothing is queued
    first = AdapterWebhookDelivery.objects.order_by("created_at").first()
    assert first.attempts == 1 and first.status == "pending" and first.next_attempt_at > now
    log = case["client"].get(hook_url(case, "/deliveries"))
    # Staff see only delivered or failed: no status code or network detail for a failed attempt (M1).
    assert log.status_code == 200 and log.data["results"][0]["last_status_code"] is None
    assert log.data["results"][0]["last_error"] == "delivery_failed"


def test_a_delivery_retries_until_it_gives_up():
    case = adapter_case("push-giveup")
    case["client"].put(hook_url(case), {"url": URL}, format="json")
    row = push.wake(case["device"], "ping")
    when = timezone.now()
    for _ in range(push.MAX_ATTEMPTS):
        when += timedelta(hours=2)
        AdapterWebhook.objects.filter(device=case["device"]).update(consecutive_failures=0)
        push.deliver(row.pk, now=when, post=lambda *a: 503)
    row.refresh_from_db()
    assert row.status == "dead" and row.attempts == push.MAX_ATTEMPTS


# --- type-profile defaults and per-binding overrides ------------------------------------------------------------------
def test_a_binding_inherits_the_type_profile_and_overrides_per_key():
    from apps.devices.services_adapter_safety import config_of
    case = adapter_case("profile-inherit", caps=CAPS)
    url = reverse("devices:admin-adapter-type-profile", args=[case["space"].pk, case["machine"].machine_type_id])
    saved = case["client"].put(url, {"auto_off_idle_minutes": 20, "require_area_clear": True, "max_session_minutes": 90,
                                     "require_filter_ok": True}, format="json")
    assert saved.status_code == 200 and case["client"].get(url).data["config"]["max_session_minutes"] == 90
    binding = AdapterBinding.objects.get(pk=case["binding_id"])
    assert config_of(binding)["auto_off_idle_minutes"] == 20
    case["client"].put(reverse("devices:admin-adapter-binding-config", args=[case["binding_id"]]),
                       {"auto_off_idle_minutes": 5}, format="json")
    binding.refresh_from_db()
    merged = config_of(binding)
    assert merged["auto_off_idle_minutes"] == 5 and merged["max_session_minutes"] == 90 and merged["require_area_clear"]
    assert AuditLog.objects.filter(action="devices.adapter_profile_set").exists()
    other = adapter_case("profile-other")
    assert other["client"].get(url).status_code in (403, 404)  # another space's staff never see this type


def test_the_filter_interlock_blocks_a_machine_until_the_filter_reports_ok():
    from apps.devices.services_adapter_access import _machine_refusal
    case = adapter_case("profile-filter", caps=CAPS)
    case["client"].put(reverse("devices:admin-adapter-binding-config", args=[case["binding_id"]]),
                       {"require_filter_ok": True}, format="json")
    binding = AdapterBinding.objects.select_related("machine").get(pk=case["binding_id"])
    member = plain_member("profile-filter-m", case["space"])
    assert _machine_refusal(binding, member, timezone.now())[1] == "filter_alert"


# --- auto-apply per binding -------------------------------------------------------------------------------------------
def test_auto_apply_is_off_by_default_and_audited_when_staff_turn_it_on():
    case = dispatched("auto-default")
    job = lease_and_ack(case)
    assert report(case, job)[1].status_code == 200
    assert PrinterJob.objects.get(pk=job["job_id"]).state == "needs_review"
    case2 = dispatched("auto-on")
    case2["client"].put(reverse("devices:admin-adapter-binding-config", args=[case2["binding_id"]]),
                        {"auto_apply_terminal": True}, format="json")
    assert AuditLog.objects.filter(action="devices.adapter_auto_apply_set").count() == 1
    job2 = lease_and_ack(case2)
    assert report(case2, job2)[1].status_code == 200
    assert PrinterJob.objects.get(pk=job2["job_id"]).state == "applied"


def test_a_failed_report_always_goes_to_review_even_with_auto_apply():
    case = dispatched("auto-failed")
    case["client"].put(reverse("devices:admin-adapter-binding-config", args=[case["binding_id"]]),
                       {"auto_apply_terminal": True}, format="json")
    job = lease_and_ack(case)
    response = report(case, job, outcome="failed", failure_reason="jam", percent_complete=30)[1]
    assert response.status_code == 200
    assert PrinterJob.objects.get(pk=job["job_id"]).state == "needs_review"


# --- max session enforcement ------------------------------------------------------------------------------------------
def _live_session(case, started_minutes_ago):
    from apps.machines.models import MachineSession
    member = plain_member(f"sess-{uuid.uuid4().hex[:6]}", case["space"])
    return MachineSession.objects.create(
        makerspace=case["space"], machine=case["machine"], machine_type=case["machine"].machine_type, member=member,
        source="device", started_at=timezone.now() - timedelta(minutes=started_minutes_ago))


def _ready(slug, minutes):
    case = adapter_case(slug, caps=CAPS)
    case["client"].put(reverse("devices:admin-adapter-binding-config", args=[case["binding_id"]]),
                       {"max_session_minutes": minutes}, format="json")
    case["sim"].post("status", {"items": [{"binding_id": case["binding_id"], "observed_at": int(time.time()),
                                           "state": "running"}]})
    return case


def test_the_sweep_warns_five_minutes_before_the_cap(monkeypatch):
    from apps.devices.services_adapter_safety import sweep_safety
    sent = []
    monkeypatch.setattr("apps.devices.adapter_notifications._send_owner", lambda row, session, text: sent.append(text))
    case = _ready("max-warn", 10)
    session = _live_session(case, 6)
    assert sweep_safety()["ending_soon"] == 1 and len(sent) == 1
    assert sweep_safety()["ending_soon"] == 0  # one notice per session
    session.refresh_from_db()
    assert session.ended_at is None


def test_the_sweep_ends_a_session_past_the_cap_and_queues_power_off():
    from apps.devices.services_adapter_safety import sweep_safety
    case = _ready("max-end", 10)
    session = _live_session(case, 12)
    assert sweep_safety()["session_ended"] == 1
    session.refresh_from_db()
    assert session.ended_at is not None and session.stop_reason == "max_length"
    command = AdapterCommand.objects.get(binding_id=case["binding_id"], capability="control")
    assert command.params == {"on": False}
    assert AuditLog.objects.filter(action="devices.adapter_auto_off", meta__reason="max_session").exists()


# --- kiosk lights the shelf --------------------------------------------------------------------------------------------
def test_a_kiosk_scan_lights_the_shelf_without_exposing_the_pose(monkeypatch):
    from tests.parity_0120.adapter_api.test_kiosk_checkout import NFC, kiosk, start, step, storage  # noqa: F401
    case = kiosk("push-kiosk")
    # The pointer is a second capability, so the adapter declares it in a fresh hello before it can be bound.
    assert case["sim"].hello(["status", "events", "checkout.kiosk", "locate.indicate"]).status_code == 200
    pointer = case["client"].post(reverse("devices:admin-adapter-binding-create", args=[case["device"].pk]),
                                  {"target_type": "space", "external_ref": "pointer", "capabilities": ["locate.indicate"]},
                                  format="json")
    assert pointer.status_code == 201, pointer.data
    AdapterPose.objects.create(makerspace=case["space"], binding_id=pointer.data["id"], target_type="item",
                               target_id=str(case["product"].pk), pose={"pan": 12, "tilt": 3})
    sid = start(case).data["session_id"]
    scanned = step(case, sid, "scan", {"qr_payload": case["qr"].payload})
    assert scanned.data["action"] == "checkout" and scanned.data["indicated"] is True
    assert "pose" not in json.dumps(scanned.data)
    command = AdapterCommand.objects.get(capability="locate.indicate", command="indicate")
    assert command.params["pose"] == {"pan": 12, "tilt": 3} and command.created_by_id is None


# --- notification catalogue --------------------------------------------------------------------------------------------
def test_the_new_device_events_are_in_the_catalogue_and_have_templates():
    from apps.integrations.email_templates_registry import get_entry
    from apps.integrations.notification_catalog import FEATURE_EVENTS
    from apps.integrations.models import NotificationFeature
    events = FEATURE_EVENTS[NotificationFeature.DEVICES]
    for event, audience in (("adapter_attention", "staff"), ("adapter_runout", "staff"),
                            ("adapter_access_denied", "staff"), ("adapter_session_ending", "requester")):
        assert event in events and get_entry("devices", audience, event) is not None


def test_the_published_envelope_schema_accepts_what_the_server_sends():
    from apps.devices.adapters.schema import errors
    from apps.devices.adapters.webhook import ENVELOPE
    case = adapter_case("push-envelope")
    case["client"].put(hook_url(case), {"url": URL, "include_data": True}, format="json")
    row = push.wake(case["device"], "command.queued", binding_id=case["binding_id"], capability="control", command="pause")
    assert errors(ENVELOPE, row.envelope) == [] and row.envelope["data"] == {"capability": "control", "command": "pause"}

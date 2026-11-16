"""Decision 321 d-g: telemetry history, diagnostics, offline access cache, remote config and signed time."""
import time
from datetime import timedelta

import pytest
from django.core.cache import cache
from django.urls import reverse
from django.utils import timezone

from apps.devices.models import AdapterAccessLog, AdapterConfigVersion, AdapterTelemetryPoint
from apps.devices.services_adapter_core import credential_digest
from tests.adapter_conformance.conformance import cache_message, time_message, verify_ed25519
from tests.parity_0120.adapter_api.adapter_case import CHILDREN, adapter_case, plain_member

pytestmark = pytest.mark.django_db(transaction=True)
HISTORY = ("status", "events", "telemetry", "telemetry.history", "sensor.report", "diagnostics")
CACHE = ("status", "events", "access.authorize", "access.cache")
ON = ("machines.integrations", *CHILDREN)


@pytest.fixture(autouse=True)
def _clear():
    cache.clear()


def _status(case, **extra):
    return case["sim"].post("status", {"items": [{"binding_id": case["binding_id"], "observed_at": int(time.time()),
                                                  "state": "running", **extra}]})


# --- d) telemetry history ---------------------------------------------------------------------------------------
def test_status_telemetry_becomes_a_series_staff_can_chart():
    case = adapter_case("hist", caps=HISTORY)
    assert _status(case, telemetry={"temperatures": {"hotend": 210.5, "bed": 60}}).data["results"][0]["result"] == "stored"
    url = reverse("devices:admin-adapter-telemetry", args=[case["binding_id"]])
    series = case["client"].get(url)
    assert series.status_code == 200 and set(series.data["series"]) == {"temp.bed", "temp.hotend"}
    points = case["client"].get(url + "?series=temp.hotend").data["points"]
    assert len(points) == 1 and points[0]["avg"] == 210.5


def test_history_is_404_when_its_switch_is_off_and_not_recorded():
    case = adapter_case("hist-off", caps=HISTORY, features=tuple(f for f in ON if not f.endswith("telemetry_history")))
    assert _status(case, telemetry={"temperatures": {"bed": 60}}).status_code == 200
    assert AdapterTelemetryPoint.objects.count() == 0
    assert case["client"].get(reverse("devices:admin-adapter-telemetry", args=[case["binding_id"]])).status_code == 404


def test_the_sweep_downsamples_raw_to_minutes_to_quarter_hours_and_expires():
    from apps.devices.services_adapter_history import sweep
    case = adapter_case("hist-sweep", caps=HISTORY)
    binding_id = case["binding_id"]
    from apps.devices.models import AdapterBinding
    binding = AdapterBinding.objects.get(pk=binding_id)
    now = timezone.now().replace(second=0, microsecond=0)
    old = now - timedelta(hours=30)
    for i, value in enumerate((10.0, 20.0, 30.0)):
        AdapterTelemetryPoint.objects.create(makerspace=binding.makerspace, binding=binding, series="temp.bed",
                                             resolution=0, ts=old + timedelta(seconds=i * 10), avg=value, min=value,
                                             max=value)
    sweep(now)
    minute = AdapterTelemetryPoint.objects.get(resolution=60)
    assert (minute.avg, minute.min, minute.max, minute.n) == (20.0, 10.0, 30.0, 3)
    assert not AdapterTelemetryPoint.objects.filter(resolution=0).exists()
    AdapterTelemetryPoint.objects.filter(resolution=60).update(ts=now - timedelta(days=8))
    sweep(now)
    quarter = AdapterTelemetryPoint.objects.get(resolution=900)
    assert quarter.n == 3 and quarter.avg == 20.0
    AdapterTelemetryPoint.objects.filter(resolution=900).update(ts=now - timedelta(days=91))
    sweep(now)
    assert AdapterTelemetryPoint.objects.count() == 0


# --- e) diagnostics ---------------------------------------------------------------------------------------------
def test_health_and_firmware_from_status_show_in_the_adapter_summary():
    case = adapter_case("diag", caps=HISTORY)
    assert _status(case, diagnostics={"health": "degraded", "firmware": "1.4.2"}).status_code == 200
    summary = case["client"].get(reverse("devices:admin-adapter-detail", args=[case["device"].pk])).data
    assert summary["health"] == "degraded" and summary["firmware"] == "1.4.2"


def test_a_log_bundle_is_requested_by_staff_and_the_adapter_uploads_it(monkeypatch):
    import uuid
    monkeypatch.setattr("apps.machines.service_storage.presigned_upload", lambda key, ct, mb: {"url": "https://s.test/u"})
    case = adapter_case("diag-bundle", caps=(*HISTORY, "artifact.upload"))
    asked = case["client"].post(reverse("devices:admin-adapter-log-bundle", args=[case["binding_id"]]))
    assert asked.status_code == 201
    unrequested = case["sim"].post("artifacts", {"operation_id": str(uuid.uuid4()), "binding_id": case["binding_id"],
                                                 "kind": "log_bundle", "content_type": "application/gzip",
                                                 "size_bytes": 100, "command_id": str(uuid.uuid4())})
    assert unrequested.status_code == 409 and unrequested.data["code"] == "log_bundle_not_requested"
    leased = case["sim"].post("commands/lease").data["command"]
    assert leased["capability"] == "diagnostics" and leased["params"]["max_bytes"] == 10 * 2 ** 20
    bundle = case["sim"].post("artifacts", {"operation_id": str(uuid.uuid4()), "binding_id": case["binding_id"],
                                            "kind": "log_bundle", "content_type": "application/gzip",
                                            "size_bytes": 100, "command_id": leased["command_id"]})
    assert bundle.status_code == 201
    from apps.devices.models import AdapterArtifact
    from apps.devices.services_adapter_artifacts import retention_days
    row = AdapterArtifact.objects.get()
    assert retention_days("log_bundle") == 7 and (row.expires_at - row.created_at).days in (6, 7)


# --- f) offline access cache ------------------------------------------------------------------------------------
def _cache_case(slug):
    case = adapter_case(slug, caps=CACHE)
    member = plain_member(f"{slug}-member", case["space"])
    made = case["client"].post(reverse("devices:admin-adapter-credentials", args=[case["space"].pk]),
                               {"user_id": member.pk, "kind": "nfc", "secret": "04A1B2C3D4"}, format="json")
    assert made.status_code == 201, made.data
    return case, member, made.data


def _digests(doc):
    return [row["digest"] for row in doc["entries"]]


def test_the_cache_is_ed25519_signed_expires_and_holds_digests_only():
    case, member, _ = _cache_case("cache-sign")
    hello = case["sim"].hello(list(CACHE))
    assert "signing_key" not in hello.data  # no symmetric secret ever travels
    keys = hello.data["cache_keys"]
    assert [row["status"] for row in keys] == ["current"] and set(keys[0]) == {"kid", "public_key", "status"}
    doc = case["sim"].get(f"access/cache?binding_id={case['binding_id']}").data
    assert doc["kid"] == keys[0]["kid"]
    assert verify_ed25519(keys, doc["kid"], cache_message(doc, _digests(doc)), doc["signature"])
    assert doc["expires_at"] - doc["issued_at"] == 900
    assert _digests(doc) == [credential_digest(case["space"].pk, "nfc", "04A1B2C3D4")]
    text = str(doc)
    assert "04A1B2C3D4" not in text and member.email not in text and "pin" not in text.lower()
    tampered = {**doc, "expires_at": doc["expires_at"] + 86400}
    assert not verify_ed25519(keys, doc["kid"], cache_message(tampered, _digests(doc)), doc["signature"])


def test_key_rotation_signs_with_the_new_kid_and_hello_keeps_the_previous_one_during_grace(settings):
    case, _member, _ = _cache_case("cache-rotate")
    old_keys = case["sim"].hello(list(CACHE)).data["cache_keys"]
    old_doc = case["sim"].get(f"access/cache?binding_id={case['binding_id']}").data
    settings.ADAPTER_CACHE_KEY_VERSION = 2
    new_keys = case["sim"].hello(list(CACHE)).data["cache_keys"]
    assert [(row["kid"], row["status"]) for row in new_keys] == [(2, "current"), (1, "previous")]
    new_doc = case["sim"].get(f"access/cache?binding_id={case['binding_id']}").data
    assert new_doc["kid"] == 2 and verify_ed25519(new_keys, 2, cache_message(new_doc, _digests(new_doc)), new_doc["signature"])
    # A cache issued before the rotation still verifies while the previous key is listed...
    assert verify_ed25519(new_keys, 1, cache_message(old_doc, _digests(old_doc)), old_doc["signature"])
    assert old_keys[0]["public_key"] == new_keys[1]["public_key"]  # same key for the same version
    # ...and stops verifying once the grace period has passed.
    settings.ADAPTER_CACHE_KEY_ROTATED_AT = int(time.time()) - 8 * 86400
    late = case["sim"].hello(list(CACHE)).data["cache_keys"]
    assert [row["kid"] for row in late] == [2]
    assert not verify_ed25519(late, 1, cache_message(old_doc, _digests(old_doc)), old_doc["signature"])


def test_revoking_a_credential_or_a_restricted_member_is_reflected_on_the_next_sync():
    from apps.devices.models import AdapterCredential
    case, member, _ = _cache_case("cache-revoke")
    url = f"access/cache?binding_id={case['binding_id']}"
    assert len(case["sim"].get(url).data["entries"]) == 1
    AdapterCredential.objects.update(disabled_at=timezone.now())
    assert case["sim"].get(url).data["entries"] == []


def test_the_cache_is_404_when_its_switch_is_off():
    case = adapter_case("cache-off", caps=CACHE, features=tuple(f for f in ON if not f.endswith("offline_cache")))
    assert case["sim"].get(f"access/cache?binding_id={case['binding_id']}").status_code == 404


def test_offline_decisions_are_reconciled_into_the_access_log_idempotently():
    import uuid
    case, member, _ = _cache_case("cache-reconcile")
    digest = credential_digest(case["space"].pk, "nfc", "04A1B2C3D4")
    case["sim"].get(f"access/cache?binding_id={case['binding_id']}")
    body = {"decisions": [{"operation_id": str(uuid.uuid4()), "binding_id": case["binding_id"], "digest": digest,
                           "allowed": True, "decided_at": int(time.time()) - 600}]}
    first = case["sim"].post("access/offline-decisions", body)
    again = case["sim"].post("access/offline-decisions", body)
    assert first.data["results"][0]["result"] == "stored" and again.data["results"][0]["result"] == "duplicate"
    row = AdapterAccessLog.objects.get(offline=True)
    assert row.allowed is True and row.member_id == member.pk and row.credential_type == "nfc"
    future = {"decisions": [{**body["decisions"][0], "operation_id": str(uuid.uuid4()),
                             "decided_at": int(time.time()) + 3600}]}
    assert case["sim"].post("access/offline-decisions", future).status_code == 400


# --- g) remote config and time ----------------------------------------------------------------------------------
def test_staff_push_a_versioned_config_the_adapter_fetches_and_acknowledges():
    case = adapter_case("config", caps=HISTORY)
    url = reverse("devices:admin-adapter-config-versions", args=[case["device"].pk])
    before = case["sim"].post("status", {"items": []}).data["config_version"]
    one = case["client"].post(url, {"config": {"poll_seconds": 30}}, format="json")
    two = case["client"].post(url, {"config": {"poll_seconds": 60, "led": True}}, format="json")
    assert (one.data["version"], two.data["version"]) == (1, 2)
    assert case["sim"].post("status", {"items": []}).data["config_version"] > before  # the adapter notices a change
    fetched = case["sim"].get("config").data
    assert fetched == {"version": 2, "config": {"poll_seconds": 60, "led": True}}
    assert case["sim"].post("config/ack", {"version": 2, "outcome": "applied"}).data["outcome"] == "applied"
    assert case["sim"].post("config/ack", {"version": 9, "outcome": "applied"}).status_code == 404
    listed = case["client"].get(url).data
    assert listed[0]["version"] == 2 and listed[0]["ack_outcome"] == "applied" and listed[1]["acked_at"] is None


def test_config_refuses_secrets_and_oversize_bodies():
    case = adapter_case("config-secret", caps=HISTORY)
    url = reverse("devices:admin-adapter-config-versions", args=[case["device"].pk])
    refused = case["client"].post(url, {"config": {"wifi": {"password": "x"}}}, format="json")
    assert refused.status_code == 400 and refused.data["code"] == "config_secret_refused"
    big = case["client"].post(url, {"config": {"blob": "x" * 20000}}, format="json")
    assert big.status_code == 413
    assert AdapterConfigVersion.objects.count() == 0


def test_server_time_is_signed_and_a_member_cannot_push_config():
    case = adapter_case("time", caps=HISTORY)
    keys = case["sim"].hello(list(HISTORY)).data["cache_keys"]
    nonce = "abc123-adapter-nonce"
    body = case["sim"].get(f"time?nonce={nonce}").data
    assert abs(body["server_time"] - time.time()) < 30 and body["nonce"] == nonce
    assert verify_ed25519(keys, body["kid"], time_message(nonce, body["kid"], body["server_time"]), body["signature"])
    assert not verify_ed25519(keys, body["kid"], time_message("other-adapter-nonce", body["kid"], body["server_time"]),
                              body["signature"])
    from tests.return_helpers import authenticated_client
    member = authenticated_client(plain_member("time-member", case["space"]))
    assert member.post(reverse("devices:admin-adapter-config-versions", args=[case["device"].pk]),
                       {"config": {}}, format="json").status_code in (403, 404)

"""Console gaps (ADAPTER-4): config keys + read-back, online/offline_since, and the staff log/job list routes."""
from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.devices.models import AdapterAccessLog, AdapterBinding, AdapterUsageLog, Device, DeviceCommand
from apps.devices.models_printers import PrinterJob
from tests.parity_0120.adapter_api.adapter_case import adapter_case

pytestmark = pytest.mark.django_db(transaction=True)
CAPS = ("status", "events", "control", "safety", "job.dispatch")


def _config_url(case):
    return reverse("devices:admin-adapter-binding-config", args=[case["binding_id"]])


def test_config_accepts_auto_apply_and_filter_keys_and_reads_back_with_sources():
    case = adapter_case("gap-config", caps=CAPS)
    type_url = reverse("devices:admin-adapter-type-profile", args=[case["space"].pk, case["machine"].machine_type_id])
    assert case["client"].put(type_url, {"max_session_minutes": 90, "require_filter_ok": True}, format="json").status_code == 200
    saved = case["client"].put(_config_url(case), {"auto_apply_terminal": True, "require_filter_ok": False,
                                                   "auto_off_idle_minutes": 7}, format="json")
    assert saved.status_code == 200, saved.data
    assert saved.data["config"] == {"auto_apply_terminal": True, "require_filter_ok": False, "auto_off_idle_minutes": 7}
    effective = saved.data["effective_config"]
    assert effective["max_session_minutes"] == {"value": 90, "source": "type"}
    assert effective["require_filter_ok"] == {"value": False, "source": "binding"}
    assert effective["auto_apply_terminal"] == {"value": True, "source": "binding"}
    detail = case["client"].get(reverse("devices:admin-adapter-binding-detail", args=[case["binding_id"]]))
    assert detail.data["config"]["auto_off_idle_minutes"] == 7
    assert detail.data["effective_config"]["max_session_minutes"]["source"] == "type"
    from apps.devices.printer_access import auto_applies
    assert auto_applies(AdapterBinding.objects.get(pk=case["binding_id"])) is True


def test_config_rejects_unknown_keys():
    case = adapter_case("gap-config-bad", caps=CAPS)
    assert case["client"].put(_config_url(case), {"nope": 1}, format="json").status_code == 400


def test_summary_reports_online_and_offline_since():
    case = adapter_case("gap-online", caps=CAPS)
    url = reverse("devices:admin-adapter-detail", args=[case["device"].pk])
    Device.objects.filter(pk=case["device"].pk).update(last_seen_at=timezone.now(), offline_since=None)
    online = case["client"].get(url).data
    assert online["online"] is True and online["offline_since"] is None
    assert "config" in online["bindings"][0] and "effective_config" in online["bindings"][0]
    since = timezone.now()
    Device.objects.filter(pk=case["device"].pk).update(offline_since=since)
    offline = case["client"].get(url).data
    assert offline["online"] is False and offline["offline_since"] is not None


def test_access_decisions_and_usage_lists_are_paginated_filtered_and_scoped():
    case = adapter_case("gap-logs", caps=CAPS)
    other = adapter_case("gap-logs-other", caps=CAPS)
    binding = AdapterBinding.objects.get(pk=case["binding_id"])
    for index, allowed in enumerate((True, False, False)):
        AdapterAccessLog.objects.create(makerspace=case["space"], device=case["device"], binding=binding,
                                        credential_type="nfc", allowed=allowed,
                                        reason="ok" if allowed else "unknown_credential")
    AdapterAccessLog.objects.create(makerspace=other["space"], device=other["device"], credential_type="pin",
                                    allowed=True, reason="ok")
    AdapterUsageLog.objects.create(makerspace=case["space"], device=case["device"], binding=binding,
                                   operation_id="0b1f6f9e-3c1d-4f43-9a5e-0a6d6f0a1111", started_at=timezone.now(),
                                   ended_at=timezone.now(), active_minutes=5, outcome="completed")
    url = reverse("devices:admin-adapter-access-decisions", args=[case["device"].pk])
    page = case["client"].get(url)
    assert page.status_code == 200 and page.data["count"] == 3
    assert set(page.data["results"][0]) == {"id", "binding", "member", "credential_type", "allowed", "reason",
                                            "session_id", "created_at"}
    assert case["client"].get(url, {"allowed": "false"}).data["count"] == 2
    assert case["client"].get(url, {"reason": "ok"}).data["count"] == 1
    assert case["client"].get(url, {"since": "not-a-date"}).status_code == 400
    usage = case["client"].get(reverse("devices:admin-adapter-usage", args=[case["device"].pk]))
    assert usage.data["count"] == 1 and usage.data["results"][0]["active_minutes"] == 5
    assert case["client"].get(reverse("devices:admin-adapter-usage", args=[other["device"].pk])).status_code in (403, 404)


def test_binding_jobs_list_shows_job_and_command_state():
    case = adapter_case("gap-jobs", caps=CAPS)
    device, machine = case["device"], case["machine"]
    command = DeviceCommand.objects.create(makerspace=case["space"], device=device, device_key_version=device.key_version,
                                           kind="printer_job", status="leased", attempts=2,
                                           lease_token_digest="0" * 64,
                                           lease_expires_at=timezone.now() + timedelta(minutes=5))
    PrinterJob.objects.create(command=command, makerspace=case["space"], device=device, machine=machine,
                              machine_id_snapshot=machine.pk, machine_name=machine.name,
                              service_request_id_snapshot=1, service_request_name="Request 1", external_job_id="ext-1",
                              state="awaiting")
    url = reverse("devices:admin-adapter-job-create", args=[case["binding_id"]])
    page = case["client"].get(url)
    assert page.status_code == 200 and page.data["count"] == 1
    row = page.data["results"][0]
    assert row["state"] == "awaiting" and row["command_status"] == "leased" and row["command_attempts"] == 2
    assert case["client"].get(url, {"state": "applied"}).data["count"] == 0

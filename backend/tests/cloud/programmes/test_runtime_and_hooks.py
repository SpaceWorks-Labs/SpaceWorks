import sys

import pytest
from django.core.exceptions import ImproperlyConfigured

from apps.events import cloud_runtime, tasks_cloud
from apps.operations.cloud_jobs.catalog import periodic_catalog
from apps.operations.cloud_jobs.contracts import JobsUnavailable


def test_full_probe_command_is_fixed_and_free_video_is_explicitly_unavailable(settings):
    settings.SPACEWORKS_DEPLOYMENT_PROFILE = "full"
    assert cloud_runtime.sandbox_command() == (sys.executable, "-m", "apps.events.submissions.probe_sandbox")
    assert cloud_runtime.video_validation_availability()["available"] is True
    settings.SPACEWORKS_DEPLOYMENT_PROFILE = "free"
    assert cloud_runtime.sandbox_command() == ()
    assert cloud_runtime.video_validation_availability() == {
        "available": False, "reason": "video_validation_unavailable_in_free_profile",
    }


def test_scanner_none_is_an_explicit_skip_and_configured_failure_never_downgrades(settings):
    settings.UPLOAD_SCAN_POLICY = "none"
    assert cloud_runtime.scan_options() == {"backend": "none"}
    settings.UPLOAD_SCAN_POLICY = "clamav"
    settings.CLAMD_HOST = ""
    with pytest.raises(ImproperlyConfigured):
        cloud_runtime.scan_options()
    settings.CLAMD_HOST = "clamav.internal"
    settings.CLAMD_PORT = 3310
    settings.CLAMD_TIMEOUT_SECONDS = 5
    settings.CLAMD_MAX_SCAN_BYTES = 10485760
    assert cloud_runtime.scan_options() == {
        "backend": "clamav", "host": "clamav.internal", "port": 3310, "max_scan_bytes": 10485760,
    }


@pytest.mark.parametrize("callback", [
    tasks_cloud.process_asset_work_task, tasks_cloud.sweep_asset_lifecycle_task,
    tasks_cloud.resume_certificates_task, tasks_cloud.cleanup_print_jobs_task,
    tasks_cloud.cleanup_programme_receipts_task, tasks_cloud.sweep_stage_file_retention_task,
])
def test_full_wrappers_cannot_become_unbounded_eager_free_jobs(settings, callback):
    settings.SPACEWORKS_DEPLOYMENT_PROFILE = "free"
    with pytest.raises(JobsUnavailable):
        callback.run()


def test_lifecycle_callback_keeps_domain_limit_and_receipt_retention(monkeypatch, settings):
    settings.SPACEWORKS_DEPLOYMENT_PROFILE = "full"
    calls = []

    def service(**kwargs):
        calls.append(kwargs)
        return {"processed": 2}

    runtime = cloud_runtime.EventCloudRuntime(service, service, service)
    monkeypatch.setattr(cloud_runtime, "_runtime", None)
    cloud_runtime.install_runtime(runtime)
    assert tasks_cloud.sweep_asset_lifecycle_task.run(limit=3) == {"processed": 2}
    tasks_cloud.cleanup_programme_receipts_task.run(limit=4)
    tasks_cloud.sweep_stage_file_retention_task.run(limit=5)
    assert calls == [{"limit": 3}, {"limit": 4, "retention_days": 30}, {"limit": 5}]


def test_programme_inventory_matches_checked_incoming_schedule_names():
    keys = {t.key for t in periodic_catalog(programmes=("pages", "events", "reimbursement"), tombstones=())}
    assert {"cleanup-public-page-assets", "event-admission-deadlines", "event-contributor-maintenance",
            "account-saved-details", "event-scheduled-broadcasts", "stage-file-retention"} <= keys


def test_full_profile_does_not_consult_free_limits(settings):
    settings.SPACEWORKS_DEPLOYMENT_PROFILE = "full"
    settings.FREE_TICK_BUDGET_SECONDS = -1
    assert tasks_cloud._full_limit(25) == 25

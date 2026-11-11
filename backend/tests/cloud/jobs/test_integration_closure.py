"""Local-only integration closure regressions; PostgreSQL runner owns execution."""
import time
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from django.db import transaction

from apps.operations.cloud_jobs import bounded, contracts, diagnostics
from apps.operations.cloud_jobs.catalog import LEGACY_ENTRIES, periodic_catalog
from apps.operations.cloud_jobs.contracts import ChunkContext, GuardLost


def context(checkpoint=None, limit=2, fence=lambda: None):
    return ChunkContext(time.monotonic() + 30, fence, checkpoint or {}, None, 1, limit)


@pytest.mark.django_db(transaction=True)
def test_page_resumes_after_completed_effect_without_offset_skips():
    rows = [SimpleNamespace(pk=pk) for pk in (1, 2, 3)]
    effects = []
    first = bounded.invoke(context(), lambda: [effects.append(row.pk) for row in bounded.page(rows, "rows")])
    assert effects == [1, 2] and not first.complete
    # A deletion between ticks cannot make PK 3 disappear behind an offset.
    second = bounded.invoke(context(first.checkpoint), lambda: [effects.append(row.pk) for row in bounded.page(rows[2:], "rows")])
    assert second.complete and effects == [1, 2, 3]


@pytest.mark.django_db(transaction=True)
def test_cursor_waits_for_database_commit():
    with bounded.scope(context()) as progress:
        with pytest.raises(RuntimeError):
            with transaction.atomic():
                for row in bounded.page([SimpleNamespace(pk=1)], "rows"):
                    pass
                assert "rows" not in progress.cursors
                raise RuntimeError("rollback")
        assert not progress.cursors and "rows" not in progress.done


@pytest.mark.django_db(transaction=True)
def test_parent_cursor_waits_for_nested_child_continuation():
    effects = []
    def callback():
        for parent in bounded.page([1], "parents"):
            for child in bounded.page([1, 2, 3], f"children:{parent}"):
                effects.append(child)
    first = bounded.invoke(context(), callback)
    assert not first.complete and effects == [1, 2]
    assert "parents" not in first.checkpoint["cursors"]
    second = bounded.invoke(context(first.checkpoint), callback)
    assert effects == [1, 2, 3] and second.complete


@pytest.mark.django_db(transaction=True)
def test_domain_catch_exception_cannot_swallow_guard_loss():
    effects = []
    def fence():
        if effects:
            raise GuardLost()
    def callback():
        for row in bounded.page([SimpleNamespace(pk=1), SimpleNamespace(pk=2)], "rows"):
            try:
                effects.append(row.pk)
            except Exception:
                pass
    with pytest.raises(GuardLost):
        bounded.invoke(context(fence=fence), callback)
    assert effects == [1]


def test_full_catalog_and_domain_bounds_ignore_free_values(settings):
    settings.SPACEWORKS_DEPLOYMENT_MODE = "host"
    settings.SPACEWORKS_DEPLOYMENT_PROFILE = "full"
    settings.FREE_TICK_SECRET = "configured-but-inert"
    settings.FREE_TICK_BUDGET_SECONDS = -999
    settings.CLOUD_PROGRAMMES = ()
    settings.TOMBSTONED_APPS = ()
    assert {(task.key, task.path, task.minutes) for task in periodic_catalog()} == set(LEGACY_ENTRIES)
    assert bounded.limit(500) == 500
    assert list(bounded.page(range(100), "unchunked")) == list(range(100))


def test_worker_nonce_is_exact_and_has_no_business_effect(monkeypatch):
    cache = Mock()
    monkeypatch.setattr(diagnostics, "cache", cache)
    for value in ("", "a" * 31, "A" * 32, "a" * 33, 123):
        with pytest.raises(ValueError):
            diagnostics.installer_roundtrip.run(value)
    cache.set.assert_not_called()
    diagnostics.installer_roundtrip.run("a" * 32)
    cache.set.assert_called_once_with("spaceworks:installer:roundtrip:" + "a" * 32, "a" * 32, timeout=60)


@pytest.mark.django_db
def test_scheduler_heartbeat_does_not_invent_work_success(monkeypatch):
    values = {}
    monkeypatch.setattr(diagnostics, "cache", SimpleNamespace(
        set=lambda key, value, timeout: values.__setitem__(key, value),
        get=lambda key, default=None: values.get(key, default)))
    diagnostics.scheduler_heartbeat("beat")
    assert diagnostics.scheduler_snapshot()["last_success_at"] is None
    diagnostics.scheduler_completed()
    assert diagnostics.scheduler_snapshot()["last_success_at"]
    diagnostics.scheduler_completed(failed=True)
    assert diagnostics.scheduler_snapshot()["failed"] is True


def test_free_catalog_has_six_persisted_queues_and_storage_maintenance(settings):
    settings.SPACEWORKS_DEPLOYMENT_MODE = "managed"
    settings.SPACEWORKS_DEPLOYMENT_PROFILE = "free"
    keys = {task.key for task in periodic_catalog(programmes=(), tombstones=())}
    assert len([key for key in keys if key.startswith("persisted-")]) == 6
    assert {"cloud-storage-qualification", "cloud-storage-usage"} <= keys


def test_free_archive_caps_refuse_before_insertion(settings, tmp_path):
    from apps.operations.cloud_jobs.admission import FreeJobTooLarge, assert_archive, assert_ciphertext
    settings.SPACEWORKS_DEPLOYMENT_PROFILE = "free"
    source = tmp_path / "input.age"
    source.write_bytes(b"x" * (2 * 1024 * 1024 + 1))
    with pytest.raises(FreeJobTooLarge, match="ciphertext"):
        assert_ciphertext(source)
    source.unlink()
    rows = tmp_path / "records.csv"
    rows.write_text("id\n" + "1\n" * 501)
    with pytest.raises(FreeJobTooLarge, match="500-row"):
        assert_archive(tmp_path)


def test_full_admission_does_not_read_free_limits_or_storage(settings, monkeypatch):
    from apps.operations.cloud_jobs import admission
    settings.SPACEWORKS_DEPLOYMENT_PROFILE = "full"
    monkeypatch.setattr(admission, "ciphertext_size", Mock(side_effect=AssertionError("must remain inert")))
    admission.assert_ciphertext("nonexistent")
    admission.assert_archive("nonexistent")
    admission.assert_export(object())


def test_failed_persisted_job_is_not_a_successful_worker_pass():
    from apps.operations.cloud_jobs.work_adapters import _require_domain_success
    from apps.operations.cloud_jobs.outcomes import TaskReportedFailure
    manager = Mock()
    manager.values_list.return_value.get.return_value = "failed"
    row = type("Row", (), {"objects": manager})()
    row.pk = 1
    with pytest.raises(TaskReportedFailure):
        _require_domain_success("staff-export", row, None)


def test_queued_actor_must_still_be_active(monkeypatch):
    from apps.operations.cloud_jobs import authority
    decision = Mock(return_value=True)
    monkeypatch.setattr(authority.rbac, "can", decision)
    actor = SimpleNamespace(is_authenticated=True, is_active=False,
                            access_status="active", must_change_password=False, retired_at=None)
    assert not authority.allowed(actor, "view_audit", 1)
    decision.assert_not_called()


def test_cancellation_requires_reviewed_exact_binding(monkeypatch):
    from apps.operations.cloud_jobs import cancellation
    template = {"version": 1, "kind": "channel", "id": "1", "attempt": 2,
        "source_sha256": "a" * 64, "configuration_sha256": "b" * 64,
        "decision": "REVIEW_REQUIRED"}
    monkeypatch.setattr(cancellation, "describe", lambda *args: dict(template))
    with pytest.raises(ValueError, match="explicit_terminal"):
        cancellation.validate(None, template)
    evidence = {**template, "decision": cancellation.DECISION}
    cancellation.validate(None, evidence)
    with pytest.raises(ValueError, match="binding_changed"):
        cancellation.validate(None, {**evidence, "attempt": 3})


@pytest.mark.django_db
def test_free_personal_claim_never_reclaimed_by_age(settings, monkeypatch):
    from datetime import timedelta
    from django.utils import timezone
    from apps.integrations import notification_delivery
    settings.SPACEWORKS_DEPLOYMENT_PROFILE = "free"
    row = SimpleNamespace(state="retrying", retryable=True, historical=False,
                          claim_until=timezone.now()-timedelta(days=3), save=Mock())
    manager = Mock()
    manager.select_for_update.return_value.get.return_value = row
    monkeypatch.setattr(notification_delivery, "Delivery", SimpleNamespace(objects=manager))
    assert notification_delivery.claim(1) is None
    row.save.assert_not_called()

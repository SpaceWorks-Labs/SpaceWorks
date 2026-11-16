"""COVERAGE-BE: every terminal outcome and refusal of the data-export job lifecycle (services.py).

Rows, statuses, failure codes and audit actions are asserted exactly; only the archive builder and
object storage (external seams) are replaced.
"""
from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.audit.models import AuditLog
from apps.data_export import services, storage
from apps.data_export.models import DataExportJob
from apps.data_export.runner import ExportDeadlineExceeded, ExportIntegrityError
from apps.makerspaces.models import Makerspace
from tests.accounts.account_factories import make_staff

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.fixture
def world(monkeypatch):
    space = Makerspace.objects.create(name="svc-cov", slug="svc-cov")
    owner = make_staff(space, username="svc-cov-owner")
    deleted = []
    monkeypatch.setattr(storage, "delete_object", lambda key: deleted.append(key) or True)
    return space, owner, deleted


def _raising(exc):
    def build(job):
        raise exc
    return build


@pytest.mark.parametrize("exc,code,detail_has", [
    (ExportIntegrityError("row 9 dangling"), "integrity_error", "row 9 dangling"),
    (ValidationError({"limit": "cap"}), "quota_exceeded", "cap"),
    (storage.ExportStorageError("bucket down"), "storage_error", "bucket down"),
    (RuntimeError("secret internal detail"), "internal_error", "The export failed unexpectedly."),
])
def test_builder_failures_become_typed_terminal_states(world, monkeypatch, exc, code, detail_has):
    space, owner, deleted = world
    job = services.create_export_job(owner, space)
    monkeypatch.setattr(services, "build_archive", _raising(exc))
    result = services.run_export_job(job.pk)
    assert (result.status, result.failure_code) == ("failed", code)
    assert detail_has in result.failure_detail
    assert "secret internal detail" not in result.failure_detail or code != "internal_error"
    assert result.accounted_size_bytes == 0 and result.download_token_digest == ""
    assert job.object_key in deleted
    assert not AuditLog.objects.filter(action="data_export.completed", target_id=str(job.pk)).exists()


def test_deadline_failure_records_progress_manifest(world, monkeypatch, settings):
    space, owner, deleted = world
    job = services.create_export_job(owner, space)
    monkeypatch.setattr(services, "build_archive", _raising(ExportDeadlineExceeded("inventory/products", 12)))
    result = services.run_export_job(job.pk)
    assert (result.status, result.failure_code) == ("failed", "deadline_exceeded")
    assert result.manifest == {
        "deadline": {"outcome": "exhausted", "seconds": settings.DATA_EXPORT_DEADLINE_SECONDS},
        "last_dataset": "inventory/products", "rows_completed": 12}
    assert job.object_key in deleted


def test_run_export_job_ignores_unknown_and_subject_jobs(world):
    space, owner, _ = world
    assert services.run_export_job("00000000-0000-0000-0000-000000000000") is None
    subject = DataExportJob.objects.create(
        makerspace=space, requested_by=owner, fidelity="SUBJECT", status="pending",
        object_key="data-exports/subject.zip", expires_at=timezone.now() + timedelta(days=1))
    assert services.run_export_job(subject.pk) is None
    subject.refresh_from_db()
    assert subject.status == "pending" and subject.started_at is None


def test_claim_job_refuses_a_job_that_is_not_pending(world):
    space, owner, _ = world
    job = services.create_export_job(owner, space)
    DataExportJob.objects.filter(pk=job.pk).update(status="running")
    assert services._claim_job(job.pk) is None
    assert services.run_export_job(job.pk) is None  # claim refused, row untouched
    job.refresh_from_db()
    assert job.status == "running" and job.started_at is None


def test_claim_job_sets_running_and_deadline_and_clears_failure(world, settings):
    space, owner, _ = world
    job = services.create_export_job(owner, space)
    DataExportJob.objects.filter(pk=job.pk).update(failure_code="storage_error", failure_detail="old")
    claimed = services._claim_job(job.pk)
    assert claimed.status == "running" and claimed.failure_code == "" and claimed.failure_detail == ""
    assert claimed.deadline_at - claimed.started_at == timedelta(seconds=settings.DATA_EXPORT_DEADLINE_SECONDS)


def test_finalize_refuses_a_job_that_left_running_and_deletes_the_object(world):
    space, owner, deleted = world
    job = services.create_export_job(owner, space)  # still pending, not running
    with pytest.raises(ExportIntegrityError, match="changed state before finalize"):
        services._finalize_job(job.pk, {"snapshot_at": timezone.now(), "row_counts": {}, "total_rows": 0}, 5)
    assert deleted == [job.object_key]
    job.refresh_from_db()
    assert job.status == "pending" and job.accounted_size_bytes == 0


def test_download_token_refused_for_subject_unavailable_and_expired_jobs(world):
    space, owner, _ = world
    base = dict(makerspace=space, requested_by=owner, fidelity="REDACTED")
    subject = DataExportJob.objects.create(
        **{**base, "fidelity": "SUBJECT"}, status="available",
        object_key="data-exports/s1.zip", expires_at=timezone.now() + timedelta(days=1))
    pending = DataExportJob.objects.create(
        **base, status="pending", object_key="data-exports/p1.zip",
        expires_at=timezone.now() + timedelta(days=1))
    expired = DataExportJob.objects.create(
        **base, status="available", object_key="data-exports/e1.zip",
        expires_at=timezone.now() - timedelta(seconds=1))
    with pytest.raises(ValidationError) as caught:
        services.issue_download_token(subject, owner)
    assert "owner download endpoint" in str(caught.value.detail["detail"])
    for job in (pending, expired):
        with pytest.raises(ValidationError) as caught:
            services.issue_download_token(job, owner)
        assert "not available for download" in str(caught.value.detail["detail"])
        job.refresh_from_db()
        assert job.download_token_digest == ""
    assert not AuditLog.objects.filter(action="data_export.download_url_issued").exists()


def _available(space, owner, key, fidelity="REDACTED"):
    return DataExportJob.objects.create(
        makerspace=space, requested_by=owner, fidelity=fidelity, status="available",
        object_key=key, expires_at=timezone.now() + timedelta(days=1))


def test_portable_token_audit_carries_format_version_zero_without_a_migration_export(world):
    space, owner, _ = world
    job = _available(space, owner, "data-exports/portable.zip", fidelity="PORTABLE")
    raw, _expires = services.issue_download_token(job, owner)
    issued = AuditLog.objects.get(action="data_export.download_url_issued", target_id=str(job.pk))
    assert issued.meta["export_id"] == str(job.pk) and issued.meta["format_version"] == 0
    claimed = services.consume_download_token(job.pk, raw)
    assert claimed.pk == job.pk
    downloaded = AuditLog.objects.get(action="data_export.downloaded", target_id=str(job.pk))
    assert downloaded.meta["export_id"] == str(job.pk) and downloaded.meta["format_version"] == 0


@pytest.mark.parametrize("mutate", ["wrong_token", "consumed", "expired_token", "no_digest", "subject", "missing"])
def test_consume_download_token_refuses_every_invalid_state(world, mutate):
    space, owner, _ = world
    job = _available(space, owner, f"data-exports/{mutate}.zip")
    raw, _ = services.issue_download_token(job, owner)
    job_id, presented = job.pk, raw
    if mutate == "wrong_token":
        presented = "x" * len(raw)
    elif mutate == "consumed":
        services.consume_download_token(job.pk, raw)
    elif mutate == "expired_token":
        DataExportJob.objects.filter(pk=job.pk).update(download_token_expires_at=timezone.now())
    elif mutate == "no_digest":
        DataExportJob.objects.filter(pk=job.pk).update(download_token_digest="")
    elif mutate == "subject":
        DataExportJob.objects.filter(pk=job.pk).update(fidelity="SUBJECT")
    elif mutate == "missing":
        job_id = "00000000-0000-0000-0000-000000000000"
    before = AuditLog.objects.filter(action="data_export.downloaded").count()
    with pytest.raises(services.DownloadTokenError, match="invalid, expired, or already used"):
        services.consume_download_token(job_id, presented)
    assert AuditLog.objects.filter(action="data_export.downloaded").count() == before

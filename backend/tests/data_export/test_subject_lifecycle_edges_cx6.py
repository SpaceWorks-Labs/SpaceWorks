"""Subject jobs recheck live access; deadline failures clean actual local artifacts."""
import json
import zipfile
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIClient

from apps.accounts.models_activity import WebSessionActivityDay
from apps.audit.models import AuditLog
from apps.data_export import storage
from apps.data_export.models import DataExportJob
from apps.data_export.runner import ExportDeadlineExceeded
from apps.data_export.subject_archive import build_subject_archive
from apps.data_export.subject_services import create_subject_export, own_jobs, run_subject_export, signed_download
from apps.makerspaces.models import Makerspace
from tests.accounts.account_factories import make_membership
from tests.accounts.ua1_helpers import person

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.fixture
def subject(monkeypatch):
    monkeypatch.setattr(timezone, "now", lambda: datetime(2026, 11, 14, 10, 30, tzinfo=UTC))
    space = Makerspace.objects.create(name="Subject edges", slug="cx6-subject-edges",
        enabled_modules=["membership", "member_accounts"], enabled_features=["membership.self_export"])
    owner = person("cx6-subject-owner")
    membership = make_membership(owner, space)
    return owner, space, membership


def test_missing_membership_refuses_creation_with_no_job_or_audit(subject):
    _, space, _ = subject
    outsider = person("cx6-subject-outsider")
    with pytest.raises(ValidationError) as error:
        create_subject_export(outsider, space)
    assert (error.value.status_code, error.value.get_codes()) == (400, {"detail": "invalid"})
    assert str(error.value.detail["detail"]) == "An active membership is required."
    assert DataExportJob.objects.filter(requested_by=outsider).count() == 0
    assert AuditLog.objects.filter(action="subject_export.requested", actor=outsider).count() == 0


@pytest.mark.parametrize("change", ["revoked", "feature_off", "member_accounts_off", "membership_off"])
def test_queued_job_rechecks_access_and_replay_does_not_duplicate_failure(subject, change, monkeypatch):
    owner, space, membership = subject
    deletions = []

    def delete(key):
        deletions.append(key)
        return True

    def upload(key, path):
        pytest.fail("An export refused for lost access must never upload an archive.")

    monkeypatch.setattr(storage, "delete_object", delete)
    monkeypatch.setattr(storage, "upload_archive", upload)
    job = create_subject_export(owner, space)
    if change == "revoked":
        membership.status = "revoked"
        membership.save(update_fields=["status"])
    elif change == "feature_off":
        space.enabled_features = []
        space.save(update_fields=["enabled_features"])
    elif change == "member_accounts_off":
        # Change persisted configuration as an import/older deployment could, to prove the execution gate.
        Makerspace.objects.filter(pk=space.pk).update(enabled_modules=["membership"])
    else:
        Makerspace.objects.filter(pk=space.pk).update(enabled_modules=["member_accounts"])
    result = run_subject_export(job.pk)
    assert deletions == [job.object_key]
    assert (result.status, result.failure_code, result.failure_detail) == (
        "failed", "internal_error", "The personal export could not be completed.")
    assert result.accounted_size_bytes == 0
    assert result.manifest == {}
    assert run_subject_export(job.pk) is None
    assert deletions == [job.object_key]
    assert AuditLog.objects.filter(action="subject_export.failed", target_id=str(job.pk)).count() == 1
    assert AuditLog.objects.get(action="subject_export.failed", target_id=str(job.pk)).meta == {"failure_code": "internal_error"}
    Makerspace.objects.filter(pk=space.pk).update(
        enabled_modules=["membership", "member_accounts"], enabled_features=["membership.self_export"])
    membership.status = "active"
    membership.save(update_fields=["status"])
    assert run_subject_export(job.pk) is None
    assert deletions == [job.object_key]
    result.refresh_from_db()
    assert (result.status, result.failure_code, result.failure_detail, result.manifest,
            result.accounted_size_bytes, result.completed_at) == (
        "failed", "internal_error", "The personal export could not be completed.", {}, 0, timezone.now())
    assert DataExportJob.objects.filter(requested_by=owner, makerspace=space).count() == 1
    assert list(AuditLog.objects.filter(target_id=str(job.pk), target_type=job._meta.label_lower)
                .order_by("pk").values_list("action", flat=True)) == [
        "subject_export.requested", "subject_export.started", "subject_export.failed"]


@pytest.mark.parametrize("disabled", ["membership", "member_accounts", "membership.self_export"])
def test_available_subject_export_survives_switch_off_and_is_readable_on_again(subject, monkeypatch, settings, disabled):
    owner, space, _ = subject
    settings.TIME_ZONE = "UTC"
    settings.DATA_EXPORT_RETENTION_SECONDS = 3600
    settings.DATA_EXPORT_DOWNLOAD_TTL_SECONDS = 600
    uploads, signatures = [], []

    def upload(key, path):
        uploads.append((key, path.stat().st_size))

    def sign(key, ttl):
        signatures.append((key, ttl))
        return "https://files.example.test/subject.zip?signature=cx6"

    monkeypatch.setattr(storage, "upload_archive", upload)
    monkeypatch.setattr(storage, "signed_archive_url", sign)
    job = run_subject_export(create_subject_export(owner, space).pk)
    assert job.status == "available"
    assert (job.started_at, job.completed_at) == (timezone.now(), timezone.now())
    assert uploads == [(job.object_key, job.accounted_size_bytes)]
    retained = DataExportJob.objects.filter(pk=job.pk).values().get()
    client = APIClient()
    client.force_authenticate(owner)
    kwargs = {"makerspace_id": space.pk, "job_id": job.pk}
    poll_url = reverse("member-subject-export-detail", kwargs=kwargs)
    download_url = reverse("member-subject-export-download", kwargs=kwargs)
    initial = client.get(poll_url)
    assert initial.status_code == 200
    assert initial.data["id"] == str(job.pk)
    assert initial.data["manifest"] == job.manifest
    expected_download = {"url": "https://files.example.test/subject.zip?signature=cx6",
                         "expires_at": "2026-11-14T10:40:00Z"}
    download = client.post(download_url)
    assert (download.status_code, download.data) == (200, expected_download)
    assert download["Cache-Control"] == "private, no-store"
    assert signatures == [(job.object_key, 600)]
    if disabled == "membership.self_export":
        Makerspace.objects.filter(pk=space.pk).update(enabled_features=[])
        kind = "feature"
    else:
        Makerspace.objects.filter(pk=space.pk).update(
            enabled_modules=[module for module in space.enabled_modules if module != disabled])
        kind = "module"
    for response in [client.get(poll_url), client.post(download_url)]:
        assert response.status_code == 404
        assert response.data["code"] == f"{kind}_disabled"
        assert response.data[kind] == disabled
    assert signatures == [(job.object_key, 600)]
    assert DataExportJob.objects.filter(pk=job.pk).values().get() == retained
    assert DataExportJob.objects.filter(makerspace=space, requested_by=owner).count() == 1
    assert list(AuditLog.objects.filter(target_id=str(job.pk), target_type=job._meta.label_lower)
                .order_by("pk").values_list("action", flat=True)) == [
        "subject_export.requested", "subject_export.started", "data_export.completed",
        "subject_export.download_url_issued"]
    Makerspace.objects.filter(pk=space.pk).update(
        enabled_modules=space.enabled_modules, enabled_features=space.enabled_features)
    restored = client.get(poll_url)
    assert (restored.status_code, restored.data) == (200, initial.data)
    download = client.post(download_url)
    assert (download.status_code, download.data) == (200, expected_download)
    assert download["Cache-Control"] == "private, no-store"
    assert signatures == [(job.object_key, 600), (job.object_key, 600)]
    assert uploads == [(job.object_key, job.accounted_size_bytes)]
    assert DataExportJob.objects.filter(pk=job.pk).values().get() == retained
    assert DataExportJob.objects.filter(makerspace=space, requested_by=owner).count() == 1
    assert list(AuditLog.objects.filter(target_id=str(job.pk), target_type=job._meta.label_lower)
                .order_by("pk").values_list("action", flat=True)) == [
        "subject_export.requested", "subject_export.started", "data_export.completed",
        "subject_export.download_url_issued", "subject_export.download_url_issued"]


def test_worker_ignores_missing_expired_and_wrong_fidelity_jobs(subject):
    owner, space, _ = subject
    assert run_subject_export(uuid4()) is None
    job = create_subject_export(owner, space)
    DataExportJob.objects.filter(pk=job.pk).update(expires_at=timezone.now() - timedelta(seconds=1))
    assert run_subject_export(job.pk) is None
    DataExportJob.objects.filter(pk=job.pk).update(expires_at=timezone.now() + timedelta(days=1), fidelity="REDACTED")
    assert run_subject_export(job.pk) is None
    job.refresh_from_db()
    assert (job.status, job.started_at, job.completed_at) == ("pending", None, None)


def test_personal_job_query_does_not_include_other_users_tenants_or_fidelities(subject):
    owner, space, _ = subject
    own = create_subject_export(owner, space)
    other = person("cx6-other-subject")
    make_membership(other, space)
    create_subject_export(other, space)
    foreign = Makerspace.objects.create(name="Other exports", slug="cx6-foreign-exports",
        enabled_modules=["membership", "member_accounts"], enabled_features=["membership.self_export"])
    make_membership(owner, foreign)
    create_subject_export(owner, foreign)
    DataExportJob.objects.create(makerspace=space, requested_by=owner, fidelity="REDACTED",
        object_key="cx6-not-subject.zip", expires_at=timezone.now() + timedelta(days=1))
    assert list(own_jobs(owner, space.pk).values_list("pk", flat=True)) == [own.pk]


def test_archive_deadline_cleans_its_temporary_directory(subject, tmp_path, monkeypatch):
    import tempfile

    owner, space, _ = subject
    job = create_subject_export(owner, space)
    job.deadline_at = timezone.now() + timedelta(minutes=5)
    ticks = iter([0, 1000000])
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))
    with pytest.raises(ExportDeadlineExceeded) as error:
        build_subject_archive(job, monotonic=lambda: next(ticks))
    assert error.value.rows_completed == 0
    assert list(tmp_path.iterdir()) == []


def test_runtime_activity_is_serialized_as_valid_json_and_scoped_to_the_owner(subject):
    owner, space, _ = subject
    today = timezone.now().date()
    other = person("cx6-runtime-other")
    for user, day in [(owner, today), (owner, today - timedelta(days=1)), (other, today)]:
        WebSessionActivityDay.objects.create(user=user, session_hash="a" * 32, makerspace=space, local_day=day)
    job = create_subject_export(owner, space)
    job.deadline_at = timezone.now() + timedelta(minutes=5)
    path, manifest, tempdir = build_subject_archive(job)
    try:
        with zipfile.ZipFile(path) as archive:
            rows = json.loads(archive.read("runtime_activity/accounts.WebSessionActivityDay.json"))
        assert len(rows) == 2
        assert {row["local_day"] for row in rows} == {today.isoformat(), (today - timedelta(days=1)).isoformat()}
        assert manifest["row_counts"]["accounts.WebSessionActivityDay"] == 2
        assert {row["makerspace_id"] for row in rows} == {space.pk}
    finally:
        tempdir.cleanup()


@pytest.mark.parametrize("status", ["pending", "running", "failed"])
def test_non_available_job_cannot_issue_a_signed_download(subject, status):
    owner, space, _ = subject
    job = create_subject_export(owner, space)
    DataExportJob.objects.filter(pk=job.pk).update(status=status)
    with pytest.raises(ValidationError) as error:
        signed_download(job, owner)
    assert (error.value.status_code, error.value.get_codes()) == (400, {"detail": "invalid"})
    assert str(error.value.detail["detail"]) == "This export is not available for download."
    assert AuditLog.objects.filter(action="subject_export.download_url_issued", target_id=str(job.pk)).count() == 0

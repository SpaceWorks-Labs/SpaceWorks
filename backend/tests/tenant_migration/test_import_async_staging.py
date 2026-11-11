"""Upload boundaries and a real encrypted staging/identity round trip."""

import csv
from datetime import timedelta
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import tarfile
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.audit.models import AuditLog
from apps.operations.models import PeriodicTaskRun
from apps.tenant_migration import import_staging, services_import_staging as staging
from apps.tenant_migration.archive_envelope import FORMAT, FORMAT_VERSION
from apps.tenant_migration.archive_stream import PORTABLE_DATASETS
from apps.tenant_migration.import_job_cleanup import resume_stale_pending_import_jobs
from apps.tenant_migration.models import TenantImportJob
from tests.tenant_migration.protocol_helpers import external_identity, superadmin

pytestmark = pytest.mark.django_db


@pytest.fixture
def actor():
    return superadmin("async-staging")


@pytest.fixture
def ops_dir(settings, tmp_path):
    settings.BACKUP_OPS_DIR = str(tmp_path / "ops")
    return Path(settings.BACKUP_OPS_DIR) / "tenant-imports"


def client_for(actor):
    client = APIClient()
    client.force_authenticate(actor)
    return client


def upload(client, payload=b"encrypted archive", **fields):
    data = {
        "archive": SimpleUploadedFile("import.tar.age", payload),
        "source_archive_digest": hashlib.sha256(payload).hexdigest(),
        **fields,
    }
    return client.post(reverse("tenant-migration-imports"), data, format="multipart")


def assert_no_upload(ops_dir):
    assert not ops_dir.exists() or list(ops_dir.iterdir()) == []
    assert not TenantImportJob.objects.exists()
    assert not AuditLog.objects.filter(
        action="tenant_migration.import_upload_received",
    ).exists()


@pytest.fixture
def pending_job(actor, ops_dir):
    def make(payload=b"encrypted archive", **overrides):
        ops_dir.mkdir(parents=True, exist_ok=True)
        path = ops_dir / f"{uuid4()}.tar.age"
        path.write_bytes(payload)
        values = {
            "actor": actor, "archive_path": str(path),
            "source_archive_digest": hashlib.sha256(payload).hexdigest(),
            "status": TenantImportJob.Status.PENDING,
            "expires_at": timezone.now() + timedelta(days=1),
            **overrides,
        }
        return TenantImportJob.objects.create(**values)
    return make


@pytest.fixture
def portable_tree(tmp_path):
    root = tmp_path / "portable"
    root.mkdir()
    identity, _private = external_identity("async-source-deployment")
    manifest = {
        "format": FORMAT, "format_version": FORMAT_VERSION,
        "source": {
            "deployment": identity,
            "makerspace": {"id": "41", "slug": "source-lab", "name": "Source Lab"},
        },
        "storage_mode": {"private": "included", "public_image": "referenced"},
    }
    (root / "migration-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    user = {
        "id": "17", "username": "archived-member", "email": "member@example.test",
        "first_name": "Archived", "last_name": "Member", "display_name": "Member",
        "phone": "", "date_joined": "2026-01-01T00:00:00Z",
        "account_kind": "member", "is_active": "true",
    }
    membership = {"id": "23", "user_id": "17", "makerspace_id": "41"}
    for label, row in (
        ("accounts.User", user), ("makerspaces.MakerspaceMembership", membership),
        ("makerspaces.Makerspace", {"id": "41", "slug": "source-lab", "name": "Source Lab"}),
    ):
        dataset = PORTABLE_DATASETS[label]
        path = root / dataset.path
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8", newline="") as output:
            writer = csv.DictWriter(output, fieldnames=[c.name for c in dataset.columns])
            writer.writeheader()
            writer.writerow(row)
    dataset = PORTABLE_DATASETS["makerspaces.MakerspaceRole"]
    path = root / dataset.path
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as output:
        csv.DictWriter(output, fieldnames=[c.name for c in dataset.columns]).writeheader()
    object_path = root / "objects" / "private" / ("ab" * 32)
    object_path.parent.mkdir(parents=True)
    object_path.write_bytes(b"private object bytes excluded from the rows sidecar")
    return SimpleNamespace(root=root, manifest=manifest, identity=identity, user=user)


@pytest.fixture
def real_archive(portable_tree, tmp_path, settings):
    if not all(shutil.which(binary) for binary in ("age", "age-keygen")):
        pytest.skip("real encrypted round trip requires age and age-keygen")
    identity = tmp_path / "age-identity.txt"
    subprocess.run(["age-keygen", "-o", str(identity)], check=True, capture_output=True)
    recipient = subprocess.run(
        ["age-keygen", "-y", str(identity)], check=True, capture_output=True, text=True,
    ).stdout.strip()
    settings.TENANT_MIGRATION_AGE_IDENTITY_FILE = str(identity)
    settings.TENANT_MIGRATION_AGE_RECIPIENT = recipient
    bundle = io.BytesIO()
    with tarfile.open(fileobj=bundle, mode="w") as archive:
        for path in sorted(portable_tree.root.rglob("*")):
            if path.is_file():
                archive.add(path, arcname=path.relative_to(portable_tree.root).as_posix())
        # Real carried-key decoding runs; no DEKs are needed for this row-only test.
        keys = b'{"keys": []}'
        info = tarfile.TarInfo("keys/deks.json")
        info.size = len(keys)
        archive.addfile(info, io.BytesIO(keys))
    ciphertext = subprocess.run(
        ["age", "-r", recipient], input=bundle.getvalue(), check=True, capture_output=True,
    ).stdout
    return SimpleNamespace(payload=ciphertext, **vars(portable_tree))


def test_post_accepts_pending_upload_and_dispatches_once(actor, ops_dir, settings, monkeypatch):
    settings.CELERY_TASK_ALWAYS_EAGER = False
    dispatch = Mock()
    monkeypatch.setattr("apps.tenant_migration.views_import.stage_import_job_task.delay", dispatch)
    payload = b"ciphertext accepted without decrypting in the request"

    response = upload(client_for(actor), payload)

    assert response.status_code == 202
    assert response.data["status"] == "pending"
    job = TenantImportJob.objects.get(pk=response.data["id"])
    assert job.actor_id == actor.pk
    assert job.source_archive_digest == hashlib.sha256(payload).hexdigest()
    assert job.status == "pending"
    path = Path(job.archive_path)
    assert path.parent == ops_dir
    assert path.read_bytes() == payload
    if os.name == "posix":
        assert stat.S_IMODE(path.stat().st_mode) == 0o600
    event = AuditLog.objects.get(action="tenant_migration.import_upload_received")
    assert event.actor_id == actor.pk
    assert event.meta == {
        "import_id": str(job.pk), "archive_bytes": len(payload), "format_version": 1,
        "source_archive_digest": job.source_archive_digest,
    }
    dispatch.assert_called_once_with(str(job.pk), actor.pk)


def test_enqueue_exception_keeps_pending_job_and_archive(actor, ops_dir, settings, monkeypatch):
    settings.CELERY_TASK_ALWAYS_EAGER = False
    dispatch = Mock(side_effect=RuntimeError("broker unavailable"))
    monkeypatch.setattr("apps.tenant_migration.views_import.stage_import_job_task.delay", dispatch)

    response = upload(client_for(actor))

    assert response.status_code == 202
    job = TenantImportJob.objects.get(pk=response.data["id"])
    assert job.status == "pending"
    assert job.failure_code == ""
    assert Path(job.archive_path).is_file()
    dispatch.assert_called_once_with(str(job.pk), actor.pk)
    dispatch.reset_mock(side_effect=True)
    now = timezone.now()
    TenantImportJob.objects.filter(pk=job.pk).update(created_at=now - timedelta(minutes=3))
    assert resume_stale_pending_import_jobs(now=now) == 1
    dispatch.assert_called_once_with(str(job.pk), actor.pk)


def test_eager_upload_waits_for_stale_sweep(
    actor, ops_dir, real_archive, settings, monkeypatch,
):
    settings.CELERY_TASK_ALWAYS_EAGER = True
    dispatch = Mock(side_effect=lambda job_id, actor_id: staging.stage_import_job(
        job_id, actor_id=actor_id,
    ))
    # Exercise staging synchronously at the scheduler boundary without relying on
    # Celery's cached app configuration; the real decrypt/seal services still run.
    monkeypatch.setattr("apps.tenant_migration.tasks.stage_import_job_task.delay", dispatch)
    response = upload(client_for(actor), real_archive.payload)
    assert response.status_code == 202
    job = TenantImportJob.objects.get(pk=response.data["id"])
    assert job.status == "pending"
    dispatch.assert_not_called()
    now = timezone.now()
    assert resume_stale_pending_import_jobs(now=now) == 0
    dispatch.assert_not_called()
    TenantImportJob.objects.filter(pk=job.pk).update(created_at=now - timedelta(minutes=3))
    # A sweep has its own five-minute lease, independent of the two-minute grace.
    assert resume_stale_pending_import_jobs(now=now + timedelta(minutes=6)) == 1
    dispatch.assert_called_once_with(str(job.pk), actor.pk)
    job.refresh_from_db()
    assert job.status == "awaiting_identity"


def test_non_superadmin_upload_is_forbidden_and_leaves_no_file(ops_dir):
    member = User.objects.create_user(username="async-member", access_status="active")
    response = upload(client_for(member))
    assert response.status_code == 403
    assert_no_upload(ops_dir)


def test_over_limit_upload_is_field_error_and_leaves_no_file(actor, ops_dir, monkeypatch):
    monkeypatch.setattr(import_staging, "MAX_ARCHIVE_BYTES", 4)
    response = upload(client_for(actor), b"five!")
    assert response.status_code == 400
    assert "archive" in response.data
    assert_no_upload(ops_dir)


def test_two_archive_parts_are_rejected_and_cleaned(actor, ops_dir):
    response = upload(client_for(actor), archive=[
        SimpleUploadedFile("first.age", b"first"),
        SimpleUploadedFile("second.age", b"second"),
    ])
    assert response.status_code == 400
    assert "archive" in response.data
    assert_no_upload(ops_dir)


def test_extra_file_field_is_rejected_and_cleaned(actor, ops_dir):
    response = upload(client_for(actor), unexpected=SimpleUploadedFile("extra.age", b"extra"))
    assert response.status_code == 400
    assert "archive" in response.data
    assert_no_upload(ops_dir)


def test_invalid_digest_is_rejected_after_upload_and_cleaned(actor, ops_dir):
    response = upload(client_for(actor), source_archive_digest="NOT-A-SHA256")
    assert response.status_code == 400
    assert "source_archive_digest" in response.data
    assert_no_upload(ops_dir)


def test_staging_seals_rows_and_identity_endpoints_survive_full_archive_deletion(
    actor, pending_job, real_archive, settings,
):
    job = pending_job(real_archive.payload)
    path = Path(job.archive_path)
    staged = staging.stage_import_job(job.pk, actor_id=actor.pk)
    job.refresh_from_db()
    assert staged.status == job.status == "awaiting_identity"
    assert (job.source_makerspace_id, job.source_makerspace_slug, job.source_makerspace_name) == (
        "41", "source-lab", "Source Lab",
    )
    assert job.source_deployment_id == real_archive.identity["deployment_id"]
    assert job.source_deployment_identity == real_archive.identity
    assert job.storage_mode == "included,referenced"
    event = AuditLog.objects.get(action="tenant_migration.import_created")
    assert event.actor_id == actor.pk
    assert event.meta == {
        "import_id": str(job.pk), "identity_count": 1, "format_version": FORMAT_VERSION,
        "source_archive_digest": job.source_archive_digest,
    }
    sidecar = Path(f"{path}.rows.age")
    assert sidecar.is_file()
    assert not Path(f"{sidecar}.part").exists()
    assert not PeriodicTaskRun.objects.filter(name=staging.staging_lease_name(job.pk)).exists()
    plaintext = subprocess.run(
        ["age", "--decrypt", "-i", settings.TENANT_MIGRATION_AGE_IDENTITY_FILE, str(sidecar)],
        check=True, capture_output=True,
    ).stdout
    with tarfile.open(fileobj=io.BytesIO(plaintext)) as archive:
        names = archive.getnames()
    assert "migration-manifest.json" in names
    assert PORTABLE_DATASETS["accounts.User"].path in names
    assert "keys/deks.json" not in names
    assert not any(name == "objects" or name.startswith("objects/") for name in names)
    path.unlink()
    client = client_for(actor)
    url = reverse("tenant-migration-import-decisions", args=(job.pk,))
    response = client.get(url)
    assert response.status_code == 200
    assert len(response.data) == 1
    assert response.data[0]["id"] == 17
    assert response.data[0]["email"] == real_archive.user["email"]
    response = client.post(url, {"decisions": [{
        "source_user_id": "17", "identity_resolution": "create_walk_in",
        "membership_disposition": "import_membership",
    }]}, format="json")
    assert response.status_code == 200
    assert response.data["status"] == "ready"
    job.refresh_from_db()
    assert job.status == "ready"
    assert job.identity_decisions.get().source_user_id == "17"
    assert sidecar.is_file()


def test_digest_mismatch_fails_and_unlinks_all_files(
    actor, pending_job, django_capture_on_commit_callbacks,
):
    job = pending_job(source_archive_digest="0" * 64)
    paths = [Path(job.archive_path), Path(f"{job.archive_path}.rows.age"),
             Path(f"{job.archive_path}.rows.age.part")]
    for path in paths[1:]:
        path.write_bytes(b"left from interrupted staging")
    with django_capture_on_commit_callbacks(execute=True):
        staging.stage_import_job(job.pk, actor_id=actor.pk)
    job.refresh_from_db()
    assert job.status == "failed"
    assert job.failure_code == "digest_mismatch"
    assert job.terminal_at is not None
    assert job.archive_path == ""
    assert all(not path.exists() for path in paths)
    assert AuditLog.objects.get(action="tenant_migration.import_staging_failed").meta == {
        "import_id": str(job.pk), "failure_code": "digest_mismatch", "format_version": 1,
    }
    assert not PeriodicTaskRun.objects.filter(name=staging.staging_lease_name(job.pk)).exists()


def test_demoted_uploader_fails_before_archive_io(
    actor, pending_job, monkeypatch, django_capture_on_commit_callbacks,
):
    job = pending_job()
    path = Path(job.archive_path)
    User.objects.filter(pk=actor.pk).update(is_active=False)
    digest = Mock(side_effect=AssertionError("demoted actor must not read the archive"))
    monkeypatch.setattr(staging, "sha256_file", digest)
    with django_capture_on_commit_callbacks(execute=True):
        staging.stage_import_job(job.pk, actor_id=actor.pk)
    job.refresh_from_db()
    assert job.status == "failed"
    assert job.failure_code == "forbidden"
    assert job.archive_path == ""
    assert not path.exists()
    assert AuditLog.objects.get(action="tenant_migration.import_staging_failed").meta["failure_code"] == "forbidden"
    digest.assert_not_called()

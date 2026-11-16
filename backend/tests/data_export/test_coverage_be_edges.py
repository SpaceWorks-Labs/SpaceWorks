"""COVERAGE-BE: exact behaviour of the small data_export modules the main suites reach only through mocks.

Storage is exercised against a recording fake S3 client (the only honest way to prove every
boto failure maps to the typed `ExportStorageError`); the rest runs against real rows.
"""
from datetime import timedelta
from types import SimpleNamespace

import pytest
from botocore.exceptions import BotoCoreError, ClientError
from django.core.cache import cache
from django.utils import timezone

from apps.accounts.models import User
from apps.audit.models import AuditLog
from apps.data_export import restore_hooks, space_pack_configuration, storage
from apps.data_export.loan_context_integrity import validate_loan_context_import
from apps.data_export.models import DataExportJob
from apps.data_export.subject_account_profile import account_profile_records
from apps.data_export.subject_services import create_subject_export
from apps.data_export.subject_tasks import run_subject_export_task, sweep_subject_exports_task
from apps.data_export.tasks import purge_expired_exports_task, run_data_export_task
from apps.data_export.throttles import DataExportCreateThrottle
from apps.makerspaces.models import Makerspace
from apps.makerspaces.models_account_profile import AccountProfile
from tests.accounts.account_factories import make_membership, make_staff

pytestmark = pytest.mark.django_db(transaction=True)


def client_error(code="500", status=500):
    return ClientError({"Error": {"Code": code}, "ResponseMetadata": {"HTTPStatusCode": status}}, "op")


class FakeS3:
    def __init__(self, *, raises=None, length=7):
        self.raises, self.length, self.calls = raises, length, []

    def _do(self, name, **kw):
        self.calls.append((name, kw))
        if self.raises:
            raise self.raises
        return {}

    def upload_fileobj(self, handle, bucket, key, ExtraArgs=None):
        self.calls.append(("upload", {"bytes": handle.read(), "bucket": bucket, "key": key, "extra": ExtraArgs}))
        if self.raises:
            raise self.raises

    def get_object(self, **kw):
        self._do("get", **kw)
        return {"Body": b"body"}

    def generate_presigned_url(self, op, Params, ExpiresIn):
        self._do("sign", op=op, params=Params, ttl=ExpiresIn)
        return "https://signed.example/x"

    def head_object(self, **kw):
        self._do("head", **kw)
        return {"ContentLength": self.length}


@pytest.fixture
def fake_s3(monkeypatch):
    def install(**kw):
        fake = FakeS3(**kw)
        monkeypatch.setattr(storage, "_client", lambda public=False: fake)
        return fake
    return install


def space(slug):
    return Makerspace.objects.create(name=slug, slug=slug)


# ---------------------------------------------------------------- storage.py
def test_upload_archive_sends_file_bytes_with_content_type(fake_s3, tmp_path, settings):
    fake = fake_s3()
    path = tmp_path / "a.zip"
    path.write_bytes(b"zipbytes")
    storage.upload_archive("data-exports/1/a.zip", str(path))
    name, kw = fake.calls[0]
    assert (name, kw["bytes"], kw["key"], kw["bucket"], kw["extra"]) == (
        "upload", b"zipbytes", "data-exports/1/a.zip", settings.AWS_STORAGE_BUCKET_NAME,
        {"ContentType": "application/zip"})


@pytest.mark.parametrize("exc", [client_error(), BotoCoreError()])
def test_upload_archive_maps_boto_failure_to_typed_error(fake_s3, tmp_path, exc):
    fake_s3(raises=exc)
    path = tmp_path / "a.zip"
    path.write_bytes(b"x")
    with pytest.raises(storage.ExportStorageError, match="could not be stored"):
        storage.upload_archive("k", str(path))


def test_upload_archive_maps_missing_local_file_to_typed_error(fake_s3, tmp_path):
    fake_s3()
    with pytest.raises(storage.ExportStorageError, match="could not be stored"):
        storage.upload_archive("k", str(tmp_path / "absent.zip"))


def test_open_archive_returns_body_and_maps_failure(fake_s3, settings):
    fake = fake_s3()
    assert storage.open_archive("k1") == b"body"
    assert fake.calls[0][1] == {"Bucket": settings.AWS_STORAGE_BUCKET_NAME, "Key": "k1"}
    fake_s3(raises=client_error())
    with pytest.raises(storage.ExportStorageError, match="could not be opened"):
        storage.open_archive("k1")


def test_signed_archive_url_is_private_attachment_and_maps_failure(fake_s3):
    fake = fake_s3()
    assert storage.signed_archive_url("k", 60) == "https://signed.example/x"
    kw = fake.calls[0][1]
    assert kw["ttl"] == 60 and kw["params"]["ResponseCacheControl"] == "private, no-store"
    assert "attachment" in kw["params"]["ResponseContentDisposition"]
    fake_s3(raises=BotoCoreError())
    with pytest.raises(storage.ExportStorageError, match="could not be signed"):
        storage.signed_archive_url("k", 60)


def test_object_size_reports_length_missing_none_and_typed_failures(fake_s3):
    fake_s3(length=42)
    assert storage.object_size("k") == 42
    for code, status in (("404", None), ("NoSuchKey", None), ("NotFound", None), ("Other", 404)):
        fake_s3(raises=client_error(code, status or 400))
        assert storage.object_size("k") is None
    fake_s3(raises=client_error("AccessDenied", 403))
    with pytest.raises(storage.ExportStorageError, match="could not be sized"):
        storage.object_size("k")
    fake_s3(raises=BotoCoreError())
    with pytest.raises(storage.ExportStorageError, match="could not be sized"):
        storage.object_size("k")


def test_delete_object_empty_key_true_success_true_failure_false(monkeypatch):
    seen = []
    monkeypatch.setattr(storage, "_client", lambda public=False: "client")
    monkeypatch.setattr(storage, "delete_all_versions", lambda client, bucket, key: seen.append((client, key)))
    assert storage.delete_object("") is True and seen == []
    assert storage.delete_object("k") is True and seen == [("client", "k")]

    def boom(client, bucket, key):
        raise client_error()
    monkeypatch.setattr(storage, "delete_all_versions", boom)
    assert storage.delete_object("k") is False


def test_client_uses_public_endpoint_only_when_asked(monkeypatch, settings):
    settings.AWS_S3_ENDPOINT_URL = "http://internal:9000"
    settings.AWS_S3_PUBLIC_ENDPOINT_URL = "http://public:9000"
    seen = []
    monkeypatch.setattr(storage, "s3_client", lambda svc, **kw: seen.append(kw["endpoint_url"]))
    storage._client()
    storage._client(public=True)
    assert seen == ["http://internal:9000", "http://public:9000"]


# ------------------------------------------------------------------ tasks.py
def test_run_data_export_task_delegates_to_run_export_job(monkeypatch):
    seen = []
    monkeypatch.setattr("apps.data_export.tasks.run_export_job", seen.append)
    run_data_export_task.run("job-1")
    assert seen == ["job-1"]


def _job(makerspace, user, *, expires_in, suffix):
    return DataExportJob.objects.create(
        makerspace=makerspace, requested_by=user, fidelity="REDACTED", status="available",
        object_key=f"data-exports/{makerspace.pk}/{suffix}.zip", expires_at=timezone.now() + expires_in)


def test_purge_deletes_only_expired_jobs_and_counts_them():
    s = space("purge-a")
    owner = make_staff(s, username="purge-owner")
    expired = _job(s, owner, expires_in=timedelta(seconds=-5), suffix="old")
    live = _job(s, owner, expires_in=timedelta(days=1), suffix="new")
    counts = purge_expired_exports_task.run()
    assert counts == {"deleted": 1, "skipped": 0}
    assert not DataExportJob.objects.filter(pk=expired.pk).exists()
    assert DataExportJob.objects.filter(pk=live.pk).exists()


def test_purge_skips_a_tenant_whose_write_gate_is_closed(monkeypatch):
    from contextlib import contextmanager

    s = space("purge-gate")
    owner = make_staff(s, username="purge-gate-owner")
    job = _job(s, owner, expires_in=timedelta(seconds=-5), suffix="gated")

    @contextmanager
    def closed(makerspace_id, *, operation, counts):
        counts["skipped"] = counts.get("skipped", 0) + 1
        yield False
    monkeypatch.setattr("apps.data_export.tasks.fanout_tenant_write", closed)
    assert purge_expired_exports_task.run() == {"deleted": 0, "skipped": 1}
    assert DataExportJob.objects.filter(pk=job.pk).exists()


# ------------------------------------------------------------ subject_tasks.py
@pytest.fixture
def subject(monkeypatch):
    cache.clear()
    member = User.objects.create_user(username="cov-subject", email="cov-subject@example.test")
    local = Makerspace.objects.create(
        name="cov-subject-tenant", slug="cov-subject-tenant",
        enabled_modules=["membership", "member_accounts"], enabled_features=["membership.self_export"])
    make_membership(member, local)
    monkeypatch.setattr(storage, "upload_archive", lambda *a: None)
    monkeypatch.setattr(storage, "delete_object", lambda *a: True)
    return member, local


def test_run_subject_export_task_runs_the_job(subject, monkeypatch):
    member, local = subject
    job = create_subject_export(member, local)
    run_subject_export_task.run(job.pk)
    job.refresh_from_db()
    assert job.status == "available"


def test_sweep_fails_a_running_job_past_its_deadline_and_audits_it(subject):
    member, local = subject
    job = create_subject_export(member, local)
    DataExportJob.objects.filter(pk=job.pk).update(
        status="running", deadline_at=timezone.now() - timedelta(minutes=1))
    counts = sweep_subject_exports_task.run()
    job.refresh_from_db()
    assert (job.status, job.failure_code) == ("failed", "deadline_exceeded")
    assert job.failure_detail == "The personal export worker deadline expired."
    assert counts == {"processed": 0, "skipped": 0}
    entry = AuditLog.objects.get(action="subject_export.failed", target_id=str(job.pk))
    assert entry.makerspace_id == local.pk and entry.meta["failure_code"] == "deadline_exceeded"


def test_sweep_leaves_a_running_job_inside_its_deadline_alone(subject):
    member, local = subject
    job = create_subject_export(member, local)
    DataExportJob.objects.filter(pk=job.pk).update(
        status="running", deadline_at=timezone.now() + timedelta(minutes=5))
    assert sweep_subject_exports_task.run() == {"processed": 0, "skipped": 0}
    job.refresh_from_db()
    assert job.status == "running"
    assert not AuditLog.objects.filter(action="subject_export.failed", target_id=str(job.pk)).exists()


def test_sweep_skips_a_tenant_with_a_closed_gate_and_runs_nothing(subject, monkeypatch):
    from contextlib import contextmanager

    member, local = subject
    job = create_subject_export(member, local)

    @contextmanager
    def closed(makerspace_id, *, operation, counts):
        counts["skipped"] = counts.get("skipped", 0) + 1
        yield False
    monkeypatch.setattr("apps.data_export.subject_tasks.fanout_tenant_write", closed)
    assert sweep_subject_exports_task.run() == {"processed": 0, "skipped": 1}
    job.refresh_from_db()
    assert job.status == "pending"


# ---------------------------------------------------------------- throttles.py
def test_create_throttle_keys_on_authenticated_post_only():
    throttle = DataExportCreateThrottle()
    user = SimpleNamespace(is_authenticated=True, pk=77)
    assert throttle.get_cache_key(SimpleNamespace(method="GET", user=user), None) is None
    assert throttle.get_cache_key(SimpleNamespace(method="POST", user=None), None) is None
    anon = SimpleNamespace(is_authenticated=False, pk=None)
    assert throttle.get_cache_key(SimpleNamespace(method="POST", user=anon), None) is None
    assert throttle.get_cache_key(SimpleNamespace(method="POST", user=user), None) == "throttle_data_export_create_77"


# ----------------------------------------------------- subject_account_profile.py
def test_account_profile_records_empty_without_a_profile():
    user = User.objects.create_user(username="no-profile", email="no-profile@example.test")
    assert account_profile_records(user) == {
        "profile": [], "projects": [], "timeline": [], "achievements": []}


def test_account_profile_records_include_only_own_profile_without_keys():
    mine = User.objects.create_user(username="prof-mine", email="prof-mine@example.test")
    theirs = User.objects.create_user(username="prof-theirs", email="prof-theirs@example.test")
    AccountProfile.objects.create(user=theirs, bio="THEIR-SECRET")
    own = AccountProfile.objects.create(user=mine, bio="my bio", avatar_key="private/avatar.png")
    out = account_profile_records(mine)
    assert len(out["profile"]) == 1 and out["profile"][0]["bio"] == "my bio"
    assert out["profile"][0]["handle"] is None
    for forbidden in ("id", "user", "avatar_key"):
        assert forbidden not in out["profile"][0]
    assert "THEIR-SECRET" not in repr(out)
    assert out["projects"] == out["timeline"] == out["achievements"] == []
    assert own.pk  # the row exists; only its safe projection is exported


# --------------------------------------------------------------- restore_hooks.py
def test_restore_hook_clears_every_copied_download_bearer_and_only_those():
    s = space("restore-hook")
    owner = make_staff(s, username="restore-owner")
    live = _job(s, owner, expires_in=timedelta(days=1), suffix="live")
    DataExportJob.objects.filter(pk=live.pk).update(
        download_token_digest="d" * 64, download_token_expires_at=timezone.now(),
        download_token_consumed_at=timezone.now(), download_issued_to=owner)
    plain = _job(s, owner, expires_in=timedelta(days=1), suffix="plain")
    assert restore_hooks.invalidate_download_tokens_after_restore() == 1
    live.refresh_from_db()
    assert (live.download_token_digest, live.download_token_expires_at,
            live.download_token_consumed_at, live.download_issued_to) == ("", None, None, None)
    assert DataExportJob.objects.get(pk=plain.pk).download_token_digest == ""


def test_strip_download_bearer_overrides_only_bearer_fields():
    fixture = {"model": "x", "fields": {"download_token_digest": "abc", "status": "available"}}
    out = restore_hooks.strip_download_bearer(fixture)
    assert out["fields"] == {"status": "available", **restore_hooks.CLEARED_DOWNLOAD_BEARER}
    assert fixture["fields"]["download_token_digest"] == "abc"  # input untouched


# ------------------------------------------------- space_pack_configuration.py
def test_pack_classification_assertion_passes_for_reviewed_sections():
    assert space_pack_configuration.assert_pack_classification() is None


def test_pack_classification_assertion_refuses_drifted_section(monkeypatch):
    drifted = space_pack_configuration.section("accounts.User", "username")
    monkeypatch.setitem(space_pack_configuration.SECTIONS, "bad", drifted)
    with pytest.raises(AssertionError):
        space_pack_configuration.assert_pack_classification()
    undeclared = space_pack_configuration.section("inventory.Category", "slug no_such_field")
    monkeypatch.setitem(space_pack_configuration.SECTIONS, "bad", undeclared)
    with pytest.raises(AssertionError):
        space_pack_configuration.assert_pack_classification()


# ---------------------------------------------------- loan_context_integrity.py
def test_loan_context_validation_accepts_a_tenant_with_no_context_rows():
    s = space("loan-ctx-empty")
    assert validate_loan_context_import(s.pk) is None

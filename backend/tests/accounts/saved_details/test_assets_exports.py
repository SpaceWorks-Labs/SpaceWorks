from datetime import timedelta
import io
from uuid import uuid4
import zipfile

import pytest
from django.utils import timezone
from pypdf import PdfWriter
from pypdf.generic import DictionaryObject, NameObject, TextStringObject

from apps.accounts.saved_details import assets, exports, storage
from apps.accounts.saved_details.errors import SavedDetailsError
from apps.accounts.saved_details.models import AccountSavedDetailsExportJob, MemberSavedAsset, SavedDetailsObjectCleanup
from apps.accounts.saved_details.pdf_validation import validate_pdf
from apps.accounts.saved_details.resume_retirement import retire_unreferenced_resumes
from apps.accounts.saved_details.resume_copy import prepare_saved_resume_selection
from apps.accounts.saved_details.workflow import change_detail
from apps.makerspaces.private_upload_transport import UploadDescriptor

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.fixture
def upload(monkeypatch):
    monkeypatch.setattr(storage, "initialize", lambda asset: UploadDescriptor(
        method="POST", url="https://storage.example/upload", fields={"key": asset.staging_key},
        expires_at=timezone.now() + timedelta(minutes=10), generation=asset.generation))


def new_asset(owner, upload, *, size=10):
    result = assets.create_resume(owner.pk, {"filename": "resume.pdf", "mime": "application/pdf", "bytes": size}, uuid4())
    return MemberSavedAsset.objects.get(pk=result["asset_id"])


def test_initialization_replays_one_asset_and_staging_only(owner, upload):
    op, body = uuid4(), {"filename": "resume.pdf", "mime": "application/pdf", "bytes": 10}
    first = assets.create_resume(owner.pk, body, op)
    second = assets.create_resume(owner.pk, body, op)
    assert first["asset_id"] == second["asset_id"]
    assert first["upload"]["fields"]["key"].startswith("staging/account/")
    assert MemberSavedAsset.objects.filter(user=owner).count() == 1
    assert not any(name in first for name in ("object_key", "verification_key"))


def test_pool_budget_includes_failed_reserved_uploads(owner, upload, settings):
    settings.PLATFORM_DOMAIN_SUFFIX = ".space.example"
    settings.ACCOUNT_SAVED_ASSET_BUDGET_BYTES = 500 * 1024**2  # managed cap cannot be lifted
    for _ in range(5):
        new_asset(owner, upload, size=10 * 1024**2)
    with pytest.raises(SavedDetailsError) as error:
        new_asset(owner, upload)
    assert error.value.status_code == 413


def test_complete_persists_work_and_worker_failure_does_not_claim_ready(owner, upload, monkeypatch):
    asset = new_asset(owner, upload)
    body = {"operation_id": uuid4(), "expected_version": 1, "generation": 1}
    assert assets.complete_resume(owner.pk, asset.pk, body)["state"] == "validating"
    monkeypatch.setattr(storage, "verify_resume", lambda _: (_ for _ in ()).throw(SavedDetailsError("scanner_unavailable", "Retry.", 503)))
    assets.validate_resume(asset.pk)
    asset.refresh_from_db()
    assert asset.state == "validating" and asset.claim_uuid is None
    assert assets.complete_resume(owner.pk, asset.pk, body)["state"] == "validating"
    monkeypatch.setattr(storage, "verify_resume", lambda _: {"sha256": "a" * 64, "scan_status": "clean", "source_version_id": "1", "final_version_id": "2"})
    assets.validate_resume(asset.pk)
    asset.refresh_from_db()
    assert asset.state == "ready" and asset.final_version_id == "2"


def test_replacement_retires_previous_original_but_not_current_or_event_copies(owner, upload):
    first, second = new_asset(owner, upload), new_asset(owner, upload)
    for asset in (first, second):
        asset.state, asset.sha256 = "ready", "a" * 64
        asset.save()
    for version, asset in enumerate((first, second)):
        change_detail(owner.pk, "resume", {"operation_id": uuid4(), "expected_version": version,
            "value": {"asset_id": asset.pk, "sha256": asset.sha256}, "save_consent": True})
    retire_unreferenced_resumes(owner.pk)
    first.refresh_from_db(); second.refresh_from_db()
    assert first.state == "deleting" and second.state == "ready"
    assert SavedDetailsObjectCleanup.objects.filter(object_keys__contains=[first.object_key]).exists()


def test_from_saved_requires_exact_selection_version_and_stops_after_selection_delete(owner, upload, monkeypatch):
    asset = new_asset(owner, upload, size=1_048_577)
    asset.state, asset.sha256 = "ready", "a" * 64
    asset.save()
    change_detail(owner.pk, "resume", {"operation_id": uuid4(), "expected_version": 0,
        "value": {"asset_id": asset.pk, "sha256": asset.sha256}, "save_consent": True})
    with pytest.raises(SavedDetailsError):
        prepare_saved_resume_selection(actor_id=owner.pk, saved_asset_id=asset.pk, saved_detail_version=2)
    reads = []
    def reader(locator, *, start, length, timeout_seconds):
        reads.append(start)
        return b"p" * length
    monkeypatch.setattr(storage, "read_range", reader)
    source = prepare_saved_resume_selection(actor_id=owner.pk, saved_asset_id=asset.pk, saved_detail_version=1)
    assert len(next(source.chunks)) == 1_048_576
    change_detail(owner.pk, "resume", {"operation_id": uuid4(), "expected_version": 1}, delete=True)
    with pytest.raises(SavedDetailsError):
        next(source.chunks)
    assert reads == [0]


def test_export_archive_has_plain_owner_values_and_24h_deadline(owner, monkeypatch):
    change_detail(owner.pk, "institution", {"operation_id": uuid4(), "expected_version": 0, "value": "Maker College", "save_consent": True})
    result = exports.create_export(owner.pk, uuid4())
    captured = {}
    monkeypatch.setattr(storage, "put_archive", lambda key, file: captured.update(key=key, data=file.read()))
    job = AccountSavedDetailsExportJob.objects.get(job_uuid=result["job_id"])
    exports.build_export(job.pk)
    job.refresh_from_db()
    assert job.state == "ready" and job.object_key == captured["key"]
    assert str(job.claim_uuid) in job.object_key
    with zipfile.ZipFile(io.BytesIO(captured["data"])) as archive:
        assert b"Maker College" in archive.read("saved-details.json")
    assert timedelta(hours=23) < job.expires_at - timezone.now() <= timedelta(hours=24)


def test_pdf_scripts_in_page_objects_are_rejected_and_plain_pdf_is_accepted():
    writer = PdfWriter(); page = writer.add_blank_page(width=100, height=100)
    stream = io.BytesIO(); writer.write(stream)
    validate_pdf(stream.getvalue())
    page[NameObject("/AA")] = DictionaryObject({NameObject("/JS"): TextStringObject("alert(1)")})
    stream = io.BytesIO(); writer.write(stream)
    with pytest.raises(SavedDetailsError):
        validate_pdf(stream.getvalue())

"""Real quota/lifecycle commands with storage and scanner transport substitutes."""
from datetime import timedelta
from io import BytesIO
from types import SimpleNamespace
from uuid import uuid4
import pytest
from django.utils import timezone
from apps.events.staged_forms import upload_jobs, upload_commands, upload_workflow
from apps.events.staged_forms.file_validation import inspect_file, FileValidationError
from apps.events.staged_forms.stage_workflow import activate_locked
from apps.events.staged_forms.trigger_service import Participant
from apps.events.staged_forms.upload_models import StageFormAsset, StageFileCleanup
from apps.events.staged_forms.retention import cleanup_one
from apps.payments.event_payouts.errors import PayoutError
from .conftest import definition, participant
from .test_inline_submission import outer

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.fixture
def stage_upload(stage_env, monkeypatch):
    env = stage_env
    registration, application = participant(env)
    row = definition(env, questions=[{"id": "file", "label": "File", "type": "file", "required": True,
        "file": {"purpose": "stage_form_file", "max_files": 2, "max_bytes_each": 10485760}}])
    with outer(env) as (event, locks):
        assignment = activate_locked(definition=row, subject=Participant(event, env.owner.pk, registration, application), locks=locks)
    monkeypatch.setattr(upload_jobs, "scan_options", lambda: {"backend": "none"})
    signed = []
    class Store:
        bucket = "test-private"
        def initialize(self, request):
            signed.append(request)
            return SimpleNamespace(method="POST", url="https://upload.invalid", fields={"key": request.staging.key},
                expires_at=request.not_after, generation=request.generation)
    monkeypatch.setattr("apps.events.staged_forms.storage.storage", Store)
    return env, row, assignment, signed


def create_file(env, row, assignment, *, size=128, operation=None):
    return upload_workflow.create(event_id=env.event.pk, stage_form_id=row.pk, actor=env.owner, data={
        "operation_id": operation or uuid4(), "expected_version": assignment.version,
        "expected_response_version": assignment.response.version, "question_id": "file", "size_bytes": size,
        "mime": "image/png", "filename": "private-filename.png"})


def test_presign_only_staging_and_identical_create_keeps_one_reservation(stage_upload):
    env, row, assignment, signed = stage_upload
    operation = uuid4()
    first = create_file(env, row, assignment, operation=operation)
    replay = create_file(env, row, assignment, operation=operation)
    asset = StageFormAsset.objects.get(pk=first["asset_id"])
    assert first["asset_id"] == replay["asset_id"]
    assert signed[0].staging.key == asset.staging_key != asset.object_key
    assert signed[0].size_bytes == 128
    assert signed[0].not_after <= asset.created_at + timedelta(minutes=15)
    assert StageFormAsset.objects.count() == StageFileCleanup.objects.count() == 1


def test_quota_reservation_and_question_count_cannot_be_bypassed(stage_upload, settings):
    env, row, assignment, _ = stage_upload
    settings.EVENT_STAGE_MEMBER_QUOTA_BYTES = 128
    create_file(env, row, assignment)
    with pytest.raises(PayoutError) as exc:
        create_file(env, row, assignment)
    assert str(exc.value.detail["code"]) == "stage_file_quota"
    assert StageFormAsset.objects.count() == 1


def test_complete_is_leased_and_decoder_scan_precede_ready(stage_upload, monkeypatch):
    from PIL import Image
    env, row, assignment, _ = stage_upload
    image = BytesIO()
    Image.new("RGB", (2, 2)).save(image, format="PNG")
    data = image.getvalue()
    created = create_file(env, row, assignment, size=len(data))
    upload_workflow.complete(event_id=env.event.pk, stage_form_id=row.pk, actor=env.owner, asset_id=created["asset_id"],
        data={"operation_id": uuid4(), "expected_version": 1, "generation": 1})
    class Store:
        def read_uploaded(self, asset):
            return data, "exact-staging-version"
        def promote_bytes(self, asset, actual, digest):
            assert actual == data
            return "exact-final-version"
    assert upload_jobs.validate_asset(created["asset_id"], store=Store()) == "ready"
    asset = StageFormAsset.objects.get(pk=created["asset_id"])
    assert asset.scan_status == "skipped"
    assert asset.final_version_id == "exact-final-version"
    assert asset.sha256 == inspect_file(data, declared_mime="image/png", expected_bytes=len(data))["sha256"]


def test_configured_unhealthy_scanner_retries_without_ready(stage_upload, monkeypatch):
    from PIL import Image
    env, row, assignment, _ = stage_upload
    image = BytesIO()
    Image.new("RGB", (2, 2)).save(image, format="PNG")
    data = image.getvalue()
    created = create_file(env, row, assignment, size=len(data))
    asset = StageFormAsset.objects.get(pk=created["asset_id"])
    asset.scanner_policy, asset.state = "clamav", "uploaded"
    asset.save()
    class Store:
        def read_uploaded(self, asset):
            return data, "v1"
        def promote_bytes(self, *args):
            pytest.fail("Unscanned bytes must never promote")
    assert upload_jobs.validate_asset(asset.pk, store=Store()) == "validating"
    asset.refresh_from_db()
    assert asset.error_code == "scanner_unavailable" and asset.lease_until > timezone.now()


def test_cleanup_failure_keeps_quota_and_durable_locators(stage_upload):
    env, row, assignment, _ = stage_upload
    created = create_file(env, row, assignment)
    asset = StageFormAsset.objects.get(pk=created["asset_id"])
    asset.expires_at = timezone.now() - timedelta(seconds=1)
    asset.save()
    cleanup = StageFileCleanup.objects.get(source_asset_id=asset.pk)
    cleanup.not_before = cleanup.next_attempt_at = asset.expires_at
    cleanup.save()
    class Failure:
        def delete(self, keys):
            raise OSError("unavailable")
    assert not cleanup_one(cleanup.pk, store=Failure())
    asset.refresh_from_db()
    cleanup.refresh_from_db()
    assert asset.state == "expired" and cleanup.last_error_code == "storage_cleanup_pending"
    class Success:
        def delete(self, keys):
            assert set(keys) == {asset.staging_key, asset.object_key}
    cleanup.next_attempt_at = timezone.now() - timedelta(seconds=1)
    cleanup.save()
    assert cleanup_one(cleanup.pk, store=Success())
    asset.refresh_from_db()
    assert asset.state == "deleted" and StageFileCleanup.objects.filter(pk=cleanup.pk).exists()


def test_real_heic_decoder_accepts_sample_and_rejects_declared_png():
    # G must install pillow-heif in the backend image; do not skip this proof.
    from PIL import Image
    import pillow_heif
    image = pillow_heif.from_pillow(Image.new("RGB", (2, 2), "blue"))
    target = BytesIO()
    image.save(target)
    data = target.getvalue()
    assert inspect_file(data, declared_mime="image/heic", expected_bytes=len(data))["canonical_mime"] == "image/heic"
    with pytest.raises(FileValidationError):
        inspect_file(data, declared_mime="image/png", expected_bytes=len(data))

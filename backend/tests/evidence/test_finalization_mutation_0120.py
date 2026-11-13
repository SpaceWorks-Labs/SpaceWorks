"""Mutation pins (decision 457) for exactly-once evidence promotion: claim, wait/recover, release, size bounds.

Storage is an in-memory dict behind the real `apps.evidence.storage` function names, so every branch of
`finalize_upload` runs against real database rows (EvidenceUploadFinalization is the coordination state).
"""
from datetime import timedelta
import uuid

import pytest
from django.utils import timezone

from apps.evidence import finalization, storage
from apps.evidence.finalization import FinalizationInProgress, finalize_upload
from apps.evidence.finalization_completed import completed_result
from apps.evidence.models import EvidenceObjectRetentionState, EvidencePhoto, EvidenceUploadFinalization
from tests.return_helpers import make_space
from tests.test_request_workflow import make_member

pytestmark = pytest.mark.django_db
MAX = 1000
Status = EvidenceUploadFinalization.Status


class FakeStore:
    def __init__(self, monkeypatch, objects):
        self.objects, self.copies, self.deleted = dict(objects), [], []
        monkeypatch.setattr(storage, "validate_evidence_object", self.validate)
        monkeypatch.setattr(storage, "copy_object", self.copy)
        monkeypatch.setattr(storage, "delete_object", self.delete)

    def validate(self, key):
        if key not in self.objects:
            raise storage.EvidenceObjectValidationError("missing", "not there")
        size = self.objects[key]
        if size == "invalid":
            raise storage.EvidenceObjectValidationError("invalid_image", "bad image")
        return storage.EvidenceValidationResult(size, "image/jpeg")

    def copy(self, source, target):
        self.copies.append((source, target))
        self.objects[target] = self.objects[source]

    def delete(self, key):
        self.deleted.append(key)
        self.objects.pop(key, None)


def _photo(slug, key):
    space = make_space(slug)
    actor = make_member(f"{slug}-staff", space)
    return EvidencePhoto.objects.create(makerspace=space, uploaded_by=actor, evidence_type="issue", object_key=key)


def test_a_staged_upload_is_promoted_once_validated_and_recorded(monkeypatch):
    photo = _photo("fin-promote", "evidence/fin-promote")
    staged = storage.staging_key(photo.object_key)
    store = FakeStore(monkeypatch, {staged: 400})
    result = finalize_upload(photo, MAX)
    assert (result.size, result.content_type) == (400, "image/jpeg")
    assert store.copies == [(staged, photo.object_key)]
    assert store.deleted == [staged]
    assert store.objects == {photo.object_key: 400}
    state = EvidenceUploadFinalization.objects.get(evidence=photo)
    assert (state.status, state.claim_token, state.size_bytes, state.content_type) == (Status.FINALIZED, None, 400, "image/jpeg")


def test_size_bounds_are_inclusive_at_both_ends(monkeypatch):
    photo = _photo("fin-bounds", "evidence/fin-bounds")
    staged = storage.staging_key(photo.object_key)
    FakeStore(monkeypatch, {staged: MAX})
    assert finalize_upload(photo, MAX).size == MAX
    other = _photo("fin-bounds-1", "evidence/fin-bounds-1")
    FakeStore(monkeypatch, {storage.staging_key(other.object_key): 1})
    assert finalize_upload(other, MAX).size == 1


@pytest.mark.parametrize("size", [0, MAX + 1])
def test_an_out_of_range_size_is_refused_as_too_large_and_the_claim_released(monkeypatch, size):
    photo = _photo(f"fin-range-{size}", f"evidence/fin-range-{size}")
    staged = storage.staging_key(photo.object_key)
    store = FakeStore(monkeypatch, {staged: size})
    with pytest.raises(storage.EvidenceObjectValidationError) as caught:
        finalize_upload(photo, MAX)
    assert caught.value.code == "too_large"
    state = EvidenceUploadFinalization.objects.get(evidence=photo)
    assert (state.status, state.claim_token) == (Status.PENDING, None)
    assert store.copies == []


def test_a_missing_staged_object_returns_none_and_releases_the_claim(monkeypatch):
    photo = _photo("fin-missing", "evidence/fin-missing")
    store = FakeStore(monkeypatch, {})
    assert finalize_upload(photo, MAX) is None
    state = EvidenceUploadFinalization.objects.get(evidence=photo)
    assert (state.status, state.claim_token) == (Status.PENDING, None)
    assert store.copies == [] and store.deleted == []


def test_an_existing_final_object_is_adopted_without_copying(monkeypatch):
    photo = _photo("fin-existing", "evidence/fin-existing")
    staged = storage.staging_key(photo.object_key)
    store = FakeStore(monkeypatch, {photo.object_key: 300, staged: 300})
    result = finalize_upload(photo, MAX)
    assert result.size == 300
    assert store.copies == [] and store.deleted == [staged]
    assert EvidenceUploadFinalization.objects.get(evidence=photo).status == Status.FINALIZED


def test_an_invalid_copied_object_is_deleted_and_the_claim_released(monkeypatch):
    photo = _photo("fin-invalid-copy", "evidence/fin-invalid-copy")
    staged = storage.staging_key(photo.object_key)
    store = FakeStore(monkeypatch, {staged: 400})
    original_copy = store.copy

    def copy_then_corrupt(source, target):
        original_copy(source, target)
        store.objects[target] = "invalid"

    monkeypatch.setattr(storage, "copy_object", copy_then_corrupt)
    with pytest.raises(storage.EvidenceObjectValidationError) as caught:
        finalize_upload(photo, MAX)
    assert caught.value.code == "invalid_image"
    assert photo.object_key in store.deleted and photo.object_key not in store.objects
    state = EvidenceUploadFinalization.objects.get(evidence=photo)
    assert (state.status, state.claim_token) == (Status.PENDING, None)


def test_a_copy_that_leaves_no_final_object_is_a_storage_failure(monkeypatch):
    photo = _photo("fin-nocopy", "evidence/fin-nocopy")
    staged = storage.staging_key(photo.object_key)
    FakeStore(monkeypatch, {staged: 400})
    monkeypatch.setattr(storage, "copy_object", lambda source, target: None)
    with pytest.raises(storage.StorageUnavailable):
        finalize_upload(photo, MAX)
    state = EvidenceUploadFinalization.objects.get(evidence=photo)
    assert (state.status, state.claim_token) == (Status.PENDING, None)


def test_an_already_finalized_upload_returns_the_recorded_result_and_drops_the_staging_copy(monkeypatch):
    photo = _photo("fin-done", "evidence/fin-done")
    EvidenceUploadFinalization.objects.create(evidence=photo, status=Status.FINALIZED, size_bytes=77, content_type="image/png")
    staged = storage.staging_key(photo.object_key)
    store = FakeStore(monkeypatch, {staged: 5})
    result = finalize_upload(photo, MAX)
    assert (result.size, result.content_type) == (77, "image/png")
    assert store.deleted == [staged] and store.copies == []


def test_a_fresh_promotion_by_someone_else_is_waited_for_and_adopted(monkeypatch):
    photo = _photo("fin-wait", "evidence/fin-wait")
    claimed = uuid.uuid4()
    EvidenceUploadFinalization.objects.create(evidence=photo, status=Status.PROMOTING, claim_token=claimed)
    staged = storage.staging_key(photo.object_key)
    store = FakeStore(monkeypatch, {photo.object_key: 250, staged: 250})
    result = finalize_upload(photo, MAX)
    assert result.size == 250
    state = EvidenceUploadFinalization.objects.get(evidence=photo)
    assert (state.status, state.claim_token, state.size_bytes) == (Status.FINALIZED, None, 250)
    assert store.deleted == [staged] and store.copies == []


def test_waiting_on_a_promotion_that_never_lands_times_out_in_progress(monkeypatch):
    photo = _photo("fin-timeout", "evidence/fin-timeout")
    EvidenceUploadFinalization.objects.create(evidence=photo, status=Status.PROMOTING, claim_token=uuid.uuid4())
    FakeStore(monkeypatch, {})
    monkeypatch.setattr(finalization, "FINALIZATION_WAIT_SECONDS", 0)
    with pytest.raises(FinalizationInProgress):
        finalize_upload(photo, MAX)
    assert EvidenceUploadFinalization.objects.get(evidence=photo).status == Status.PROMOTING


def test_the_wait_returns_the_result_another_worker_finalized_meanwhile(monkeypatch):
    photo = _photo("fin-meanwhile", "evidence/fin-meanwhile")
    EvidenceUploadFinalization.objects.create(evidence=photo, status=Status.PROMOTING, claim_token=uuid.uuid4())
    FakeStore(monkeypatch, {})

    def other_worker_finishes(_seconds):
        EvidenceUploadFinalization.objects.filter(evidence=photo).update(status=Status.FINALIZED, size_bytes=9, content_type="image/webp")

    monkeypatch.setattr(finalization.time, "sleep", other_worker_finishes)
    monkeypatch.setattr(finalization, "FINALIZATION_WAIT_SECONDS", 5)
    result = finalize_upload(photo, MAX)
    assert (result.size, result.content_type) == (9, "image/webp")


def test_a_stale_promotion_is_reclaimed_but_a_fresh_one_is_not(monkeypatch, settings):
    settings.EVIDENCE_URL_TTL_SECONDS = 120
    photo = _photo("fin-stale", "evidence/fin-stale")
    staged = storage.staging_key(photo.object_key)
    state = EvidenceUploadFinalization.objects.create(evidence=photo, status=Status.PROMOTING, claim_token=uuid.uuid4())
    # Just inside the window: someone else still owns it, so we wait rather than promote.
    EvidenceUploadFinalization.objects.filter(pk=photo.pk).update(updated_at=timezone.now() - timedelta(seconds=110))
    store = FakeStore(monkeypatch, {staged: 400})
    monkeypatch.setattr(finalization, "FINALIZATION_WAIT_SECONDS", 0)
    with pytest.raises(FinalizationInProgress):
        finalize_upload(photo, MAX)
    assert store.copies == []
    # Just past it: reclaimed and promoted by us.
    EvidenceUploadFinalization.objects.filter(pk=photo.pk).update(updated_at=timezone.now() - timedelta(seconds=130))
    assert finalize_upload(photo, MAX).size == 400
    assert store.copies == [(staged, photo.object_key)]
    state.refresh_from_db()
    assert state.status == Status.FINALIZED


def test_the_stale_window_has_a_sixty_second_floor(monkeypatch, settings):
    settings.EVIDENCE_URL_TTL_SECONDS = 5
    photo = _photo("fin-floor", "evidence/fin-floor")
    EvidenceUploadFinalization.objects.create(evidence=photo, status=Status.PROMOTING, claim_token=uuid.uuid4())
    EvidenceUploadFinalization.objects.filter(pk=photo.pk).update(updated_at=timezone.now() - timedelta(seconds=50))
    FakeStore(monkeypatch, {})
    monkeypatch.setattr(finalization, "FINALIZATION_WAIT_SECONDS", 0)
    with pytest.raises(FinalizationInProgress):
        finalize_upload(photo, MAX)


def test_evidence_claimed_for_expiry_cannot_be_promoted_or_reused(monkeypatch):
    photo = _photo("fin-expiring", "evidence/fin-expiring")
    EvidenceObjectRetentionState.objects.create(evidence=photo)
    FakeStore(monkeypatch, {storage.staging_key(photo.object_key): 4})
    with pytest.raises(storage.EvidenceObjectValidationError) as caught:
        finalize_upload(photo, MAX)
    assert caught.value.code == "expired"
    EvidenceUploadFinalization.objects.update_or_create(evidence=photo, defaults={"status": Status.FINALIZED, "size_bytes": 4})
    with pytest.raises(storage.EvidenceObjectValidationError) as again:
        completed_result(photo)
    assert again.value.code == "expired"


def test_completed_result_is_database_only_and_none_until_finalized():
    photo = _photo("fin-completed", "evidence/fin-completed")
    assert completed_result(photo) is None
    EvidenceUploadFinalization.objects.create(evidence=photo, status=Status.PROMOTING)
    assert completed_result(photo) is None
    EvidenceUploadFinalization.objects.filter(evidence=photo).update(status=Status.FINALIZED, size_bytes=12, content_type="image/gif")
    result = completed_result(photo)
    assert (result.size, result.content_type) == (12, "image/gif")


def test_releasing_a_claim_only_works_for_the_claim_holder():
    photo = _photo("fin-release", "evidence/fin-release")
    token = uuid.uuid4()
    EvidenceUploadFinalization.objects.create(evidence=photo, status=Status.PROMOTING, claim_token=token)
    finalization._release_claim(photo.pk, uuid.uuid4())
    state = EvidenceUploadFinalization.objects.get(evidence=photo)
    assert (state.status, state.claim_token) == (Status.PROMOTING, token)
    finalization._release_claim(photo.pk, token)
    state.refresh_from_db()
    assert (state.status, state.claim_token) == (Status.PENDING, None)
    EvidenceUploadFinalization.objects.filter(evidence=photo).update(status=Status.FINALIZED, claim_token=token)
    finalization._release_claim(photo.pk, token)
    state.refresh_from_db()
    assert state.status == Status.FINALIZED


def test_completing_twice_keeps_the_first_recorded_result():
    photo = _photo("fin-twice", "evidence/fin-twice")
    EvidenceUploadFinalization.objects.create(evidence=photo, status=Status.PROMOTING)
    first = finalization._complete(photo.pk, storage.EvidenceValidationResult(10, "image/jpeg"))
    second = finalization._complete(photo.pk, storage.EvidenceValidationResult(99, "image/png"))
    assert (first.size, second.size, second.content_type) == (10, 10, "image/jpeg")


def test_attachment_lock_refuses_only_when_a_retention_state_exists():
    photo = _photo("fin-lock", "evidence/fin-lock")
    assert finalization.lock_evidence_for_attachment(photo.pk) is True
    EvidenceObjectRetentionState.objects.create(evidence=photo)
    assert finalization.lock_evidence_for_attachment(photo.pk) is False

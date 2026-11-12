"""Decision 337c: a photo batch stuck after a broker loss is resumed under a row lock, and closed only if that fails."""
import pytest
from django.utils import timezone

from apps.card_designs import photo_batch_apply
from apps.card_designs.models import CardPhotoBatch, CardPhotoBatchItem
from .test_photo_batch import _add, _create, _space, _url, applied, no_broker  # noqa: F401
from tests.l3_local.helpers import client

from .conftest import jpeg

pytestmark = pytest.mark.django_db


def _stalled_batch(slug):
    space, sm, cards = _space(slug)
    api = client(sm)
    batch_id = _create(api, space).json()["id"]
    _add(api, space, batch_id, ("TNK-0001.jpg", jpeg()), ("TNK-0002.jpg", jpeg()))
    assert api.post(_url(space, "admin-card-photo-batch-apply", batch_id)).status_code == 202
    # The worker never ran (broker lost) and the batch has now passed its expiry.
    CardPhotoBatch.objects.filter(pk=batch_id).update(expires_at=timezone.now())
    return batch_id, cards


def test_a_stalled_batch_is_resumed_and_finished_not_closed_as_expired(store, applied):
    batch_id, cards = _stalled_batch("pb-resume")
    assert photo_batch_apply.expire_stalled() == 0  # nothing had to be closed
    batch = CardPhotoBatch.objects.get(pk=batch_id)
    assert (batch.state, batch.applied_count, batch.skipped_count) == ("done", 2, 0)
    assert sorted(pk for _actor, pk, _size in applied) == sorted([cards["a"].pk, cards["b"].pk])
    assert not CardPhotoBatchItem.objects.filter(error_code="expired").exists()
    assert not CardPhotoBatchItem.objects.exclude(file_key="").exists()


def test_a_batch_whose_resume_fails_is_closed_and_its_photos_are_deleted(store, applied, monkeypatch):
    batch_id, _cards = _stalled_batch("pb-resume-fails")

    def broken(_batch_id):
        raise RuntimeError("storage down")

    monkeypatch.setattr(photo_batch_apply, "apply_chunk", broken)
    assert photo_batch_apply.expire_stalled() == 1
    batch = CardPhotoBatch.objects.get(pk=batch_id)
    assert batch.state == "done" and batch.applied_count == 0 and batch.skipped_count == 2
    assert set(CardPhotoBatchItem.objects.values_list("error_code", flat=True)) == {"expired"}
    assert not applied and not CardPhotoBatchItem.objects.exclude(file_key="").exists()


def test_a_batch_that_finished_meanwhile_is_left_alone(store, applied):
    batch_id, _cards = _stalled_batch("pb-resume-done")
    CardPhotoBatch.objects.filter(pk=batch_id).update(state="done")
    assert photo_batch_apply.expire_stalled() == 0
    assert not applied

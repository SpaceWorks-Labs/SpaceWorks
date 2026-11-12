"""SECURITY-REVIEW M10, M11 and L-M2 for cut-outs and bulk photo upload.

M10: a cut-out whose storage charge is refused at the cap frees nothing (it was never charged); a failed write after
a successful charge frees exactly that charge and drops the partial object.
M11: an upload is planned without reading photo bytes, then read, re-encoded, stored and dropped one photo at a
time; one zip and a byte budget per upload; oversized placeholders count against the batch cap; a refusal found
while reading deletes what the upload already stored. L-M2: the batch cap is re-checked under the batch lock.
"""
import zipfile
from io import BytesIO

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.exceptions import ValidationError

from apps.card_designs import cutouts, photo_batch, photo_batch_apply
from apps.card_designs import photo_batch_intake as intake
from apps.card_designs.models import CardPhotoBatch, CardPhotoBatchItem, CardPhotoCutout
from tests.l3_local.helpers import client

from .conftest import jpeg
from .test_cutouts import _answer, _setup, _staff_url
from .test_photo_batch import _add, _create, _space

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def no_broker(monkeypatch):
    monkeypatch.setattr("apps.card_designs.tasks.dispatch_cutout", lambda cutout_id: None)
    monkeypatch.setattr(photo_batch_apply.cutouts, "request", lambda *a, **k: None, raising=False)


# --- M10 --------------------------------------------------------------------------------------------------------

@pytest.fixture
def queued(monkeypatch, store, original_photo):
    _space_row, sm, _user, card = _setup("m10")
    _answer(monkeypatch)
    assert client(sm).post(_staff_url(card), {}, format="json").status_code == 202
    return CardPhotoCutout.objects.get()


@pytest.fixture
def ledger(monkeypatch):
    calls = {"charged": [], "freed": []}
    monkeypatch.setattr("apps.makerspaces.limits_usage.free_storage", lambda space, size: calls["freed"].append(size))
    return calls


def test_a_refused_charge_frees_nothing(monkeypatch, queued, ledger, store):
    def at_cap(space, size):
        raise ValidationError({"detail": "storage full"})
    monkeypatch.setattr("apps.makerspaces.limits_usage.add_storage", at_cap)
    assert cutouts.run(queued.pk) is None
    queued.refresh_from_db()
    assert (queued.state, queued.error_code) == ("failed", "storage_unavailable")
    assert ledger["freed"] == []                         # repeated requests can no longer drain storage_bytes_used
    assert not [key for key in store if key.startswith("card-cutouts/")]


def test_a_failed_write_frees_exactly_the_charge_and_drops_the_object(monkeypatch, queued, ledger, store):
    monkeypatch.setattr("apps.makerspaces.limits_usage.add_storage",
                        lambda space, size: ledger["charged"].append(size))

    def broken(key, data, content_type):
        store[key] = data[:3]                             # a partial object
        raise OSError("storage down")
    monkeypatch.setattr(cutouts, "put_bytes", broken)
    cutouts.run(queued.pk)
    assert ledger["freed"] == ledger["charged"] and len(ledger["charged"]) == 1
    assert not [key for key in store if key.startswith("card-cutouts/")]


def test_a_successful_cut_out_is_charged_once_and_never_freed(monkeypatch, queued, ledger, store):
    monkeypatch.setattr("apps.makerspaces.limits_usage.add_storage",
                        lambda space, size: ledger["charged"].append(size))
    cutouts.run(queued.pk)
    queued.refresh_from_db()
    assert queued.state == "done" and len(ledger["charged"]) == 1 and ledger["freed"] == []


# --- M11: planning --------------------------------------------------------------------------------------------

def _zip(entries, name="photos.zip"):
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for entry, data in entries:
            archive.writestr(entry, data)
    return SimpleUploadedFile(name, buffer.getvalue())


class Unread(SimpleUploadedFile):
    """An upload that fails if anything reads it: planning must not."""

    def read(self, *args, **kwargs):
        raise AssertionError("planning read the photo bytes")


def test_planning_reads_no_photo_bytes_and_loading_reads_one():
    plan = intake.plan_uploads([Unread("a.jpg", jpeg()), SimpleUploadedFile("b.jpg", jpeg())])
    try:
        assert [name for name, _load in plan.photos] == ["a.jpg", "b.jpg"]
        assert plan.photos[1][1]() == jpeg()
    finally:
        plan.close()


def test_only_one_zip_per_upload():
    with pytest.raises(ValidationError):
        intake.plan_uploads([_zip([("a.jpg", jpeg())]), _zip([("b.jpg", jpeg())], name="more.zip")])
    plan = intake.plan_uploads([_zip([("a.jpg", jpeg())]), SimpleUploadedFile("b.jpg", jpeg())])
    plan.close()
    assert len(plan.photos) == 2


def test_the_per_upload_byte_budget_counts_files_and_zip_entries_together(monkeypatch):
    monkeypatch.setattr(intake, "MAX_REQUEST_BYTES", len(jpeg()) * 2)
    intake.plan_uploads([SimpleUploadedFile("a.jpg", jpeg()), _zip([("b.jpg", jpeg())])]).close()
    with pytest.raises(ValidationError):
        intake.plan_uploads([SimpleUploadedFile("a.jpg", jpeg()), _zip([("b.jpg", jpeg()), ("c.jpg", jpeg())])])


def test_oversized_placeholders_count_against_the_batch_cap(monkeypatch):
    monkeypatch.setattr(intake, "MAX_UPLOAD_BYTES", 10)
    monkeypatch.setattr(intake, "MAX_FILES", 2)
    with pytest.raises(ValidationError):
        intake.plan_uploads([SimpleUploadedFile(f"{n}.jpg", b"x" * 50) for n in range(3)])


# --- M11 / L-M2: storing ----------------------------------------------------------------------------------------

def _batch_keys(store):
    return [key for key in store if key.startswith("card-photo-batches/")]


def _add_raw(api, space, batch_id, upload):
    from django.urls import reverse
    url = reverse("admin-card-photo-batch-files", args=[space.pk, batch_id])
    return api.post(url, {"files": [upload]}, format="multipart")


def test_a_refusal_found_while_reading_deletes_what_was_already_stored(store):
    space, sm, _cards = _space("m11-clean")
    api = client(sm)
    batch_id = _create(api, space).json()["id"]
    upload = _zip([("TNK-0001.jpg", jpeg()), ("TNK-0002.jpg", jpeg()), ("evil.jpg", b"PK\x03\x04" + b"0" * 50)])
    response = _add_raw(api, space, batch_id, upload)
    assert response.status_code == 400
    assert _batch_keys(store) == [] and not CardPhotoBatchItem.objects.exists()


def test_a_normal_upload_still_stores_and_matches_every_photo(store):
    space, sm, _cards = _space("m11-ok")
    api = client(sm)
    batch_id = _create(api, space).json()["id"]
    body = _add(api, space, batch_id, ("TNK-0001.jpg", jpeg()), ("TNK-0002.jpg", jpeg())).json()
    assert body["file_count"] == 2 and len(_batch_keys(store)) == 2
    assert [item["decision"] for item in body["items"]] == ["apply", "apply"]


def test_two_uploads_racing_past_the_cap_are_refused_under_the_lock(monkeypatch, store):
    space, sm, _cards = _space("lm2-batch")
    api = client(sm)
    batch_id = _create(api, space).json()["id"]
    stale = CardPhotoBatch.objects.get(pk=batch_id)        # read before the other upload landed
    monkeypatch.setattr(intake, "MAX_FILES", 1)
    assert _add(api, space, batch_id, ("TNK-0001.jpg", jpeg())).status_code == 200
    kept = set(_batch_keys(store))
    with pytest.raises(ValidationError):
        photo_batch.add_files(stale, space, None, [SimpleUploadedFile("TNK-0002.jpg", jpeg())])
    assert set(_batch_keys(store)) == kept                  # the loser's photo was deleted again
    assert CardPhotoBatchItem.objects.filter(batch_id=batch_id).count() == 1

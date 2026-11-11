from datetime import datetime, UTC, timedelta
from types import SimpleNamespace
import hashlib

import pytest

from apps.events.submissions.errors import SubmissionError
from apps.events.submissions.storage import EventAssetStorage
from apps.events.submissions.storage_promotion import promote
from apps.events.submissions.storage_cleanup import delete_keys
from .fake_storage import FakeS3


def asset(**patch):
    values = dict(staging_key="staging/owned", verification_key="verification/owned", object_key="final/owned",
                  declared_bytes=4, declared_mime="application/octet-stream", effective_cap=100,
                  multipart_upload_id="", part_size=0, upload_not_after=datetime.now(UTC)+timedelta(minutes=15))
    return SimpleNamespace(**{**values, **patch})


def test_exact_post_never_signs_verification_or_final():
    fake = FakeS3()
    storage = EventAssetStorage(fake, fake, "private")
    descriptor, upload_id, _ = storage.initialize(asset(), now=datetime.now(UTC))
    assert descriptor["fields"]["key"] == "staging/owned"
    assert upload_id == ""
    assert ["content-length-range", 4, 4] in fake.signed["Conditions"]


def test_overwrite_after_verification_cannot_change_ready_hash():
    fake = FakeS3()
    storage = EventAssetStorage(fake, fake, "private")
    fake.put_object(Bucket="private", Key="staging/owned", Body=b"good")
    source = storage.complete(asset())
    frozen = storage.freeze(source, "verification/owned")
    fake.put_object(Bucket="private", Key="staging/owned", Body=b"evil")
    digest = hashlib.sha256(b"good").hexdigest()
    final = promote(storage, source=frozen, target_key="final/owned", sha256=digest, mime="application/octet-stream")
    assert storage.digest(final) == digest
    assert storage.digest(storage.head("staging/owned")) != digest
    # Crash after final-copy reconciles identical bytes, never overwrites.
    assert promote(storage, source=frozen, target_key="final/owned", sha256=digest, mime="application/octet-stream") == final
    fake.put_object(Bucket="private", Key="foreign-final", Body=b"evil")
    with pytest.raises(SubmissionError, match="final key collision"):
        promote(storage, source=frozen, target_key="foreign-final", sha256=digest, mime="application/octet-stream")


def test_multipart_server_list_proves_order_size_and_etag():
    fake = FakeS3()
    storage = EventAssetStorage(fake, fake, "private")
    ident = fake.create_multipart_upload(Bucket="private", Key="staging/owned")["UploadId"]
    row = asset(multipart_upload_id=ident, part_size=2)
    fake.upload_part(Bucket="private", Key=row.staging_key, UploadId=ident, PartNumber=2, Body=b"cd")
    with pytest.raises(SubmissionError):
        storage.list_parts(row)
    fake.upload_part(Bucket="private", Key=row.staging_key, UploadId=ident, PartNumber=1, Body=b"ab")
    assert [p["PartNumber"] for p in storage.list_parts(row)] == [1, 2]
    assert storage.complete(row).size == 4


@pytest.mark.parametrize("numbers", [[0], [1, 1], [3], [True], [], list(range(1, 102))])
def test_part_refresh_rejects_duplicate_outside_and_unbounded_numbers(numbers):
    fake = FakeS3()
    storage = EventAssetStorage(fake, fake, "private")
    with pytest.raises(SubmissionError):
        storage.sign_parts(asset(multipart_upload_id="issued-only", part_size=2), numbers)


def test_cleanup_deletes_all_versions_and_owned_multipart_only():
    fake = FakeS3()
    storage = EventAssetStorage(fake, fake, "private")
    for content in (b"a", b"b"):
        fake.put_object(Bucket="private", Key="staging/owned", Body=content)
    fake.put_object(Bucket="private", Key="staging/owned-other", Body=b"neighbor")
    fake.create_multipart_upload(Bucket="private", Key="staging/owned")
    delete_keys(storage, ["staging/owned"])
    assert not fake.objects["staging/owned"] and not fake.multipart
    assert fake.objects["staging/owned-other"]

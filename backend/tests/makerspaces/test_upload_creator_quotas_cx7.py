"""Storage creators use fresh usage, including repeated calls with a stale tenant."""
import pytest
from django.db import connection
from rest_framework.exceptions import APIException

from apps.evidence.finalization import charge_storage_once
from apps.evidence.models import EvidenceUploadFinalization
from apps.makerspaces.limits_uploads import charge_upload
from tests.limits_0120.creator_races_cx7 import race_creators
from tests.return_helpers import make_issue_evidence, make_member, make_space

pytestmark = [pytest.mark.django_db, pytest.mark.area_inventory, pytest.mark.area_lending]


def world(key):
    space = make_space("cx7-upload-creator")
    space.resource_limit_overrides = {key: 1}
    space.save(update_fields=["resource_limit_overrides"])
    return space


@pytest.mark.parametrize("key", ["storage", "storage_public_images_bytes", "upload_bytes"])
def test_public_upload_max_and_next_refusal_reuse_the_same_space_instance(key, settings):
    settings.MANAGED_PLANS_ENABLED = False
    space = world(key)
    charge_upload(space, 1)
    # Do not refresh the caller's instance: a form may process several images.
    assert space.storage_bytes_used == 0
    with pytest.raises(APIException) as raised:
        charge_upload(space, 2 if key == "upload_bytes" else 1)
    code = {"storage": "limit_reached", "upload_bytes": "upload_limit",
            "storage_public_images_bytes": "storage_public_images_bytes_quota_reached"}[key]
    assert raised.value.status_code == (409 if key == "storage_public_images_bytes" else 400)
    assert str(raised.value.detail["code"]) == code
    space.refresh_from_db()
    assert space.storage_bytes_used == 1


def evidence_rows(space):
    actor = make_member("cx7-evidence-creator", space)
    photos = [make_issue_evidence(space, actor) for _ in range(2)]
    for photo in photos:
        EvidenceUploadFinalization.objects.create(evidence=photo, status="finalized", size_bytes=1)
    return photos


def test_evidence_storage_max_and_next_refusal_preserve_the_uncharged_sidecar(settings):
    settings.MANAGED_PLANS_ENABLED = False
    settings.STORAGE_PRESIGN_METHOD = "put"
    space = world("storage_evidence_bytes")
    first, second = evidence_rows(space)
    charge_storage_once(first, 1)
    assert EvidenceUploadFinalization.objects.get(evidence=first).quota_charged is True
    before = list(EvidenceUploadFinalization.objects.order_by("pk").values())
    with pytest.raises(APIException) as raised:
        charge_storage_once(second, 1)
    assert raised.value.status_code == 409
    assert str(raised.value.detail["code"]) == "storage_evidence_bytes_quota_reached"
    assert list(EvidenceUploadFinalization.objects.order_by("pk").values()) == before
    charge_storage_once(first, 1)
    space.refresh_from_db()
    assert space.storage_bytes_used == 1


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("key", ["storage", "storage_public_images_bytes", "storage_evidence_bytes"])
def test_two_upload_creators_racing_for_last_byte_admit_one(key, settings):
    if connection.vendor != "postgresql":
        pytest.skip("Requires PostgreSQL row locks")
    settings.MANAGED_PLANS_ENABLED = False
    settings.STORAGE_PRESIGN_METHOD = "put"
    space = world(key)
    if key == "storage_evidence_bytes":
        photos = evidence_rows(space)
        create = lambda index: charge_storage_once(photos[index], 1)
    else:
        create = lambda index: charge_upload(space, 1)
    expected = (400, "limit_reached") if key == "storage" else (409, f"{key}_quota_reached")
    assert race_creators(create) == [(201, "created"), expected]
    space.refresh_from_db()
    assert space.storage_bytes_used == 1
    if key == "storage_evidence_bytes":
        assert EvidenceUploadFinalization.objects.filter(evidence__makerspace=space, quota_charged=True).count() == 1


@pytest.mark.django_db(transaction=True)
def test_upload_bytes_is_a_per_file_cap_so_two_concurrent_max_files_both_fit(settings):
    if connection.vendor != "postgresql":
        pytest.skip("Requires PostgreSQL row locks")
    settings.MANAGED_PLANS_ENABLED = False
    space = world("upload_bytes")
    assert race_creators(lambda _: charge_upload(space, 1)) == [(201, "created"), (201, "created")]
    space.refresh_from_db()
    assert space.storage_bytes_used == 2

"""PUT and POST evidence must share inclusive quotas and exactly-once accounting."""
import pytest
from django.db import connection

from apps.audit.models import AuditLog
from apps.evidence.finalization import charge_storage_once
from apps.evidence.models import EvidencePhoto, EvidenceUploadFinalization
from apps.makerspaces.models import Makerspace, StorageQuotaReservation
from rest_framework.exceptions import APIException
from tests.limits_0120.creator_races_cx7 import race_creators
from tests.inventory.test_creator_limit_concurrency_cx7 import callers
from tests.return_helpers import make_issue_evidence, make_member, make_space

pytestmark = [pytest.mark.django_db, pytest.mark.area_lending, pytest.mark.area_inventory]
KEYS = [("upload_bytes", 400, "upload_limit"), ("storage", 400, "limit_reached"),
        ("storage_evidence_bytes", 409, "storage_evidence_bytes_quota_reached")]


def world(key, settings):
    settings.MANAGED_PLANS_ENABLED = False
    space = make_space("p4a-evidence-transports")
    space.resource_limit_overrides = {key: 1}
    space.save(update_fields=["resource_limit_overrides"])
    actor = make_member("p4a-evidence-manager", space)
    photos = [make_issue_evidence(space, actor) for _ in range(2)]
    for photo in photos:
        EvidenceUploadFinalization.objects.create(evidence=photo, status="finalized", size_bytes=1)
    return space, photos


def snapshot(space):
    return (Makerspace.objects.get(pk=space.pk).storage_bytes_used,
            list(StorageQuotaReservation.objects.order_by("pk").values()),
            list(EvidencePhoto.objects.order_by("pk").values()),
            list(EvidenceUploadFinalization.objects.order_by("pk").values()),
            list(AuditLog.objects.filter(makerspace=space).order_by("pk").values()))


@pytest.mark.parametrize("transport", ["put", "post"])
@pytest.mark.parametrize("key,status,code", KEYS)
def test_transport_max_next_refusal_and_replay_do_not_mutate_evidence(
        transport, key, status, code, settings):
    settings.STORAGE_PRESIGN_METHOD = transport
    space, photos = world(key, settings)
    charge_storage_once(photos[0], 1)
    before = snapshot(space)
    assert before[0] == 1
    with pytest.raises(APIException) as raised:
        charge_storage_once(photos[1], 2 if key == "upload_bytes" else 1)
    assert (raised.value.status_code, str(raised.value.detail["code"])) == (status, code)
    assert snapshot(space) == before
    charge_storage_once(photos[0], 1)
    assert snapshot(space) == before


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("transport", ["put", "post"])
@pytest.mark.parametrize("key,status,code", KEYS[1:])
def test_evidence_transports_race_for_one_remaining_byte(transport, key, status, code, settings):
    if connection.vendor != "postgresql":
        pytest.skip("Requires PostgreSQL row locks")
    settings.STORAGE_PRESIGN_METHOD = transport
    space, photos = world(key, settings)
    assert race_creators(lambda index: charge_storage_once(photos[index], 1)) == [
        (201, "created"), (status, code)]
    assert Makerspace.objects.get(pk=space.pk).storage_bytes_used == 1
    assert EvidenceUploadFinalization.objects.filter(evidence__makerspace=space, quota_charged=True).count() == 1


@pytest.mark.parametrize("surface", ["browser", "apple", "android"])
@pytest.mark.parametrize("key,code", [("upload_bytes", "upload_limit"), ("storage", "limit_reached")])
def test_evidence_presign_declared_max_next_refusal_writes_no_photo_or_audit(key, code, surface, settings, monkeypatch):
    from unittest.mock import Mock
    from apps.evidence import services_upload
    space = make_space("p4a-evidence-presign")
    space.resource_limit_overrides = {key: 1}
    space.save(update_fields=["resource_limit_overrides"])
    caller = callers(space, surface, settings, monkeypatch)[0]
    provider = Mock(return_value={"url": "https://upload.example.test", "fields": {}})
    monkeypatch.setattr(services_upload, "presigned_upload", provider)
    url = f"/api/v1/admin/makerspaces/{space.pk}/uploads/evidence-url"
    body = {"evidence_type": "issue", "content_type": "image/png", "size_bytes": 1}
    assert caller.post(url, body, format="json").status_code == 201
    photo = EvidencePhoto.objects.get(makerspace=space)
    provider.assert_called_once_with(photo.object_key, "image/png", max_bytes=1, exact_bytes=1)
    before = snapshot(space)
    provider.reset_mock()
    refused = caller.post(url, {**body, "size_bytes": 2}, format="json")
    assert (refused.status_code, refused.json()["code"]) == (400, code)
    assert snapshot(space) == before
    provider.assert_not_called()


@pytest.mark.parametrize("surface", ["browser", "apple", "android"])
def test_evidence_upload_module_off_preserves_rows_on_restores_same_payload(surface, settings, monkeypatch):
    from apps.evidence import services_upload
    space = make_space("p4a-evidence-switch")
    caller = callers(space, surface, settings, monkeypatch)[0]
    original = list(space.enabled_modules)
    space.enabled_modules = [key for key in original if key != "evidence_uploads"]
    space.save(update_fields=["enabled_modules"])
    from unittest.mock import Mock
    provider = Mock(return_value={"url": "https://upload.example.test", "fields": {}})
    monkeypatch.setattr(services_upload, "presigned_upload", provider)
    url = f"/api/v1/admin/makerspaces/{space.pk}/uploads/evidence-url"
    body = {"evidence_type": "issue", "content_type": "image/png"}
    before = snapshot(space)
    refused = caller.post(url, body, format="json")
    assert (refused.status_code, refused.json()["code"]) == (404, "module_disabled")
    assert snapshot(space) == before
    space.enabled_modules = original
    space.save(update_fields=["enabled_modules"])
    assert caller.post(url, body, format="json").status_code == 201
    photo = EvidencePhoto.objects.get(makerspace=space)
    reservation = StorageQuotaReservation.objects.get(object_key=photo.object_key)
    provider.assert_called_once_with(photo.object_key, "image/png", max_bytes=reservation.size_bytes)
    assert reservation.converted is False
    assert reservation.released is False


def test_control_evidence_upload_creator_is_routeless_even_for_superadmin(client):
    from django.contrib import admin
    from django.urls import reverse
    from tests.accounts.reauth_helpers import force_recent_control_login
    from tests.r2_superadmin_local.helpers import superadmin
    force_recent_control_login(client, superadmin("p4a-evidence-control-root"))
    registered = admin.site._registry[EvidencePhoto]
    from django.test import RequestFactory
    request = RequestFactory().get("/control/")
    request.user = superadmin("p4a-evidence-control-other-root")
    assert registered.has_add_permission(request) is False
    before = EvidencePhoto.objects.count()
    url = reverse("admin:evidence_evidencephoto_add")
    assert client.get(url).status_code == 403
    assert client.post(url, {}).status_code == 403
    assert EvidencePhoto.objects.count() == before

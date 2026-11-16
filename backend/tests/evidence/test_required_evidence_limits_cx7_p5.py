"""529.1: required issue/return photos fitting quota complete their real workflows."""
from unittest.mock import Mock

import pytest
from django.urls import reverse

from apps.audit.models import AuditLog
from apps.evidence import storage
from apps.evidence.models import EvidencePhoto, EvidenceUploadFinalization
from apps.hardware_requests.models import HardwareRequest
from apps.makerspaces.models import MakerspaceMembership, StorageQuotaReservation
from tests.inventory.test_creator_limit_concurrency_cx7 import callers
from tests.return_helpers import (make_space, make_product, make_issued_request, return_url, return_payload)
from tests.test_issue import (make_accepted_request, assign_scanned_box, make_box, issue_url, issue_payload)

pytestmark = [pytest.mark.django_db, pytest.mark.area_lending, pytest.mark.area_inventory]


@pytest.mark.parametrize("surface", ["browser", "apple", "android"])
@pytest.mark.parametrize("transport", ["put", "post"])
@pytest.mark.parametrize("kind", ["issue", "return"])
@pytest.mark.parametrize("quota_lowered", [False, True])
@pytest.mark.parametrize("key,status,code", [
    ("storage", 400, "limit_reached"), ("storage_evidence_bytes", 409, "storage_evidence_bytes_quota_reached")])
def test_required_photo_fits_presign_and_real_workflow_next_upload_has_typed_refusal(
        surface, transport, kind, quota_lowered, key, status, code, settings, monkeypatch):
    settings.STORAGE_PRESIGN_METHOD = transport
    settings.MANAGED_PLANS_ENABLED = False
    space = make_space("p5-required-evidence")
    space.resource_limit_overrides = {key: 10}
    space.save(update_fields=["resource_limit_overrides"])
    caller = callers(space, surface, settings, monkeypatch)[0]
    actor = MakerspaceMembership.staff_tracks.get(makerspace=space).user
    product = make_product(space)
    if kind == "issue":
        request = make_accepted_request(space, product, 1)
        assign_scanned_box(request, make_box(space), actor)
    else:
        request = make_issued_request(space, actor, [(product, 1)])
    provider = Mock(return_value={"url": "https://storage.test/upload", "fields": {}})
    monkeypatch.setattr("apps.evidence.services_upload.presigned_upload", provider)
    url = reverse("evidence_admin:evidence-upload-url", kwargs={"makerspace_id": space.pk})
    body = {"evidence_type": kind, "content_type": "image/png", "size_bytes": 10}
    signed = caller.post(url, body, format="json")
    assert signed.status_code == 201
    photo = EvidencePhoto.objects.get(pk=signed.json()["evidence_id"])
    objects = {storage.staging_key(photo.object_key): 10}

    def validate(key):
        if key not in objects:
            raise storage.EvidenceObjectValidationError("missing", "not uploaded")
        return storage.EvidenceValidationResult(objects[key], "image/png")

    def copy(source, target):
        objects[target] = objects[source]

    monkeypatch.setattr(storage, "validate_evidence_object", validate)
    monkeypatch.setattr(storage, "copy_object", copy)
    monkeypatch.setattr(storage, "delete_object", lambda key: objects.pop(key, None))
    previous_status = request.status
    previous_stock = (product.available_quantity, product.reserved_quantity, product.issued_quantity)
    if quota_lowered:
        space.resource_limit_overrides = {key: 9}
        space.save(update_fields=["resource_limit_overrides"])
    if kind == "issue":
        response = caller.post(issue_url(request), issue_payload(photo), format="json")
    else:
        response = caller.post(return_url(request), return_payload(request, photo), format="json")
    if quota_lowered:
        assert (response.status_code, response.json()["code"]) == (status, code)
        request.refresh_from_db()
        product.refresh_from_db()
        assert request.status == previous_status
        assert (product.available_quantity, product.reserved_quantity, product.issued_quantity) == previous_stock
        row = StorageQuotaReservation.objects.get(object_key=photo.object_key)
        assert (row.converted, row.released, row.size_bytes) == (False, False, 10)
        assert objects[photo.object_key] == 10
        assert EvidenceUploadFinalization.objects.get(evidence=photo).quota_charged is False
        return
    assert response.status_code == 200, response.content
    request.refresh_from_db()
    assert request.status == (HardwareRequest.Status.ISSUED if kind == "issue" else HardwareRequest.Status.RETURNED)
    assert EvidenceUploadFinalization.objects.get(evidence=photo).quota_charged is True
    assert StorageQuotaReservation.objects.get(object_key=photo.object_key).converted is True
    photo.refresh_from_db()
    assert photo.consumption_state == "consumed"
    product.refresh_from_db()
    assert product.issued_quantity == (1 if kind == "issue" else 0)
    assert AuditLog.objects.filter(makerspace=space, action="request.issued" if kind == "issue" else "request.returned").count() == 1
    space.refresh_from_db()
    assert space.storage_bytes_used == 10
    refused = caller.post(url, {**body, "size_bytes": 1}, format="json")
    assert (refused.status_code, refused.json()["code"]) == (status, code)
    assert EvidencePhoto.objects.filter(makerspace=space).count() == 1


@pytest.mark.parametrize("contact", [False, True])
def test_self_checkout_presign_uses_the_same_durable_reservation(contact, settings, monkeypatch):
    from apps.hardware_requests import self_checkout_contact
    from tests.return_helpers import make_member
    from rest_framework.exceptions import APIException
    space = make_space("p5-public-evidence")
    actor = make_member("p5-public-uploader", space)
    space.resource_limit_overrides = {"storage": 10}
    space.save(update_fields=["resource_limit_overrides"])
    monkeypatch.setattr(self_checkout_contact, "presigned_upload", Mock(return_value={"url": "https://upload.test", "fields": {}}))
    body = {"evidence_type": "issue", "content_type": "image/png", "size_bytes": 10}
    kwargs = {"uploader": actor, "actor": None if contact else actor,
              "contact_email": "confirmed@example.test" if contact else None}
    assert self_checkout_contact.issue_upload(space, body, **kwargs).status_code == 201
    assert StorageQuotaReservation.objects.get(makerspace=space).size_bytes == 10
    with pytest.raises(APIException) as failure:
        self_checkout_contact.issue_upload(space, body, **kwargs)
    assert (failure.value.status_code, str(failure.value.detail["code"])) == (400, "limit_reached")

"""Exercise presign, staging promotion and handover with no cloud selectors."""
import os
from unittest.mock import Mock

import pytest
from django.urls import reverse

from apps.evidence import storage
from apps.evidence.models import EvidencePhoto, EvidenceUploadFinalization
from apps.hardware_requests.models import HardwareRequest
from tests.test_issue import (
    assign_scanned_box, authenticated_client, issue_payload, issue_url,
    make_accepted_request, make_box, make_member, make_product, make_space,
)


@pytest.mark.django_db
def test_no_cloud_post_upload_can_be_finalized_and_issued(settings, monkeypatch):
    for name in tuple(os.environ):
        if name.startswith(("CLOUD_", "FREE_", "SPACEWORKS_DEPLOYMENT_")):
            monkeypatch.delenv(name)
    # Match the unset/default host/full profile; no cloud capability file or PUT.
    settings.SPACEWORKS_DEPLOYMENT_MODE = "host"
    settings.SPACEWORKS_DEPLOYMENT_PROFILE = "full"
    settings.STORAGE_CAPABILITIES_FILE = ""
    settings.STORAGE_PRESIGN_METHOD = "post"
    space = make_space("full-evidence")
    actor = make_member("full-evidence-staff", space)
    product = make_product(space)
    request = make_accepted_request(space, product, 1)
    assign_scanned_box(request, make_box(space), actor)
    client = authenticated_client(actor)
    monkeypatch.setattr("apps.hardware_requests.notifications.notify_request_issued", lambda *args: None)
    presign = Mock(return_value={"url": "https://storage.test/upload", "fields": {"key": "staging-only"}})
    monkeypatch.setattr("apps.evidence.services_upload.presigned_upload", presign)
    response = client.post(reverse("evidence_admin:evidence-upload-url", kwargs={"makerspace_id": space.pk}), {
        "evidence_type": "issue", "content_type": "image/jpeg",
    }, format="json")
    assert response.status_code == 201, response.data
    photo = EvidencePhoto.objects.get(pk=response.data["evidence_id"])
    presign.assert_called_once_with(photo.object_key, "image/jpeg")
    staged = storage.staging_key(photo.object_key)
    objects, copies = {staged: 123}, []

    def validate(key):
        if key not in objects:
            raise storage.EvidenceObjectValidationError("missing", "not uploaded")
        return storage.EvidenceValidationResult(objects[key], "image/jpeg")

    def copy(source, target):
        copies.append((source, target))
        objects[target] = objects[source]

    monkeypatch.setattr(storage, "validate_evidence_object", validate)
    monkeypatch.setattr(storage, "copy_object", copy)
    monkeypatch.setattr(storage, "delete_object", lambda key: objects.pop(key, None))
    charge = Mock(side_effect=AssertionError("POST must retain presign-time accounting"))
    monkeypatch.setattr("apps.makerspaces.limits.add_storage", charge)
    response = client.post(issue_url(request), issue_payload(photo), format="json")
    assert response.status_code == 200, response.data
    request.refresh_from_db()
    assert request.status == HardwareRequest.Status.ISSUED
    assert copies == [(staged, photo.object_key)]
    assert objects == {photo.object_key: 123}
    state = EvidenceUploadFinalization.objects.get(evidence=photo)
    assert state.status == "finalized" and state.size_bytes == 123
    assert not state.quota_charged
    charge.assert_not_called()


@pytest.mark.django_db
def test_put_finalization_charges_only_once(settings, monkeypatch):
    from apps.evidence.finalization import charge_storage_once

    settings.STORAGE_PRESIGN_METHOD = "put"
    space = make_space("put-evidence")
    actor = make_member("put-evidence-staff", space)
    photo = EvidencePhoto.objects.create(makerspace=space, uploaded_by=actor,
        evidence_type="issue", object_key="evidence/put-once")
    EvidenceUploadFinalization.objects.create(evidence=photo, status="finalized", size_bytes=123)
    charge = Mock()
    monkeypatch.setattr("apps.makerspaces.limits.add_storage", charge)
    charge_storage_once(photo, 123)
    charge_storage_once(photo, 123)
    charge.assert_called_once_with(space, 123)

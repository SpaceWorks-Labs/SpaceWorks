"""MOD-1: the handover Hard Rules asserted exactly -- the refusal AND that no state moved.

Complements test_issue / test_return_validation, which assert the status and code but not that the
request, stock, scans, evidence and audit log are all untouched after the refusal.
"""
from unittest.mock import Mock

import pytest

from apps.audit.models import AuditLog
from apps.boxes.models import BoxScan
from apps.evidence.models import EvidencePhoto
from apps.hardware_requests.models import HardwareRequest, HardwareRequestItem, ReturnEvent
from apps.inventory.models import InventoryProduct
from tests.return_helpers import (
    authenticated_client, make_accepted_request, make_box, make_issued_request, make_issue_evidence, make_member,
    make_product, make_return_evidence, make_space, return_payload, return_url)

pytestmark = pytest.mark.django_db


def _reserve(product, quantity, total):
    """make_accepted_request adds no reservation; mirror what the workflow's accept does."""
    InventoryProduct.objects.filter(pk=product.pk).update(
        available_quantity=total - quantity, reserved_quantity=quantity)


def _snapshot(request, product, evidence):
    request.refresh_from_db(); product.refresh_from_db(); evidence.refresh_from_db()
    return (request.status, request.issued_by_id, request.issue_evidence_id,
            product.available_quantity, product.reserved_quantity, product.issued_quantity,
            BoxScan.objects.count(), AuditLog.objects.count(), evidence.consumption_state)


def test_issue_without_a_box_scan_is_refused_400_and_nothing_moves(monkeypatch):
    space = make_space("m1-hr-noscan")
    admin = make_member("m1-hr-noscan-admin", space)
    product = make_product(space, total_quantity=5, available_quantity=5)
    request = make_accepted_request(space, product, 2)
    _reserve(product, 2, 5)
    request.assigned_box = make_box(space)
    request.save(update_fields=["assigned_box"])
    evidence = make_issue_evidence(space, admin)
    monkeypatch.setattr("apps.evidence.storage.object_exists", Mock(return_value=True))
    before = _snapshot(request, product, evidence)

    response = authenticated_client(admin).post(
        f"/api/v1/admin/requests/{request.pk}/issue", {"evidence_id": evidence.pk, "remark": "x"}, format="json")

    assert response.status_code == 400 and response.data["code"] == "validation_error"
    assert _snapshot(request, product, evidence) == before
    assert before[0] == HardwareRequest.Status.ACCEPTED
    assert before[3:6] == (3, 2, 0)  # still reserved, nothing issued


def test_issue_without_an_uploaded_photo_is_refused_409_and_nothing_moves(monkeypatch):
    space = make_space("m1-hr-nophoto")
    admin = make_member("m1-hr-nophoto-admin", space)
    product = make_product(space, total_quantity=5, available_quantity=5)
    request = make_accepted_request(space, product, 1)
    box = make_box(space)
    request.assigned_box = box
    request.save(update_fields=["assigned_box"])
    BoxScan.objects.create(makerspace=space, box=box, request=request, actor=admin, context=BoxScan.Context.ISSUE)
    evidence = make_issue_evidence(space, admin)
    monkeypatch.setattr("apps.evidence.storage.object_exists", Mock(return_value=False))
    before = _snapshot(request, product, evidence)

    response = authenticated_client(admin).post(
        f"/api/v1/admin/requests/{request.pk}/issue", {"evidence_id": evidence.pk, "remark": "x"}, format="json")

    assert response.status_code == 409 and response.data["code"] == "evidence_not_uploaded"
    assert _snapshot(request, product, evidence) == before
    assert before[8] != "consumed"  # the unused presign is not marked consumed


@pytest.mark.parametrize("remark", ["", "   ", "\t\n"])
def test_return_with_a_blank_or_whitespace_remark_is_refused_and_nothing_moves(monkeypatch, remark):
    space = make_space(f"m1-hr-remark-{len(remark)}-{ord(remark[0]) if remark else 0}")
    admin = make_member(f"m1-hr-remark-admin-{len(remark)}-{ord(remark[0]) if remark else 0}", space)
    product = make_product(space, total_quantity=5, available_quantity=5)
    request = make_issued_request(space, admin, [(product, 2)])
    evidence = make_return_evidence(space, admin)
    monkeypatch.setattr("apps.evidence.storage.object_exists", Mock(return_value=True))
    before = _snapshot(request, product, evidence)

    response = authenticated_client(admin).post(
        return_url(request), return_payload(request, evidence, remark=remark), format="json")

    assert response.status_code == 400
    assert "remark" in response.data or response.data.get("code") == "validation_error"
    assert _snapshot(request, product, evidence) == before
    assert before[0] == HardwareRequest.Status.ISSUED and before[5] == 2
    assert ReturnEvent.objects.count() == 0


def test_return_without_evidence_id_is_refused_400_and_the_loan_stays_out(monkeypatch):
    space = make_space("m1-hr-noevid")
    admin = make_member("m1-hr-noevid-admin", space)
    product = make_product(space)
    request = make_issued_request(space, admin, [(product, 1)])
    payload = return_payload(request, make_return_evidence(space, admin))
    del payload["evidence_id"]
    response = authenticated_client(admin).post(return_url(request), payload, format="json")
    assert response.status_code == 400
    request.refresh_from_db()
    assert request.status == HardwareRequest.Status.ISSUED and ReturnEvent.objects.count() == 0


def test_issued_quantity_equals_the_accepted_quantity_never_the_requested_one(monkeypatch, settings):
    from apps.evidence.storage import EvidenceValidationResult
    settings.STORAGE_PRESIGN_METHOD = "post"
    space = make_space("m1-hr-issued-le-accepted")
    admin = make_member("m1-hr-issued-le-accepted-admin", space)
    product = make_product(space, total_quantity=10, available_quantity=10)
    request = make_accepted_request(space, product, 2)
    _reserve(product, 2, 10)
    item = request.items.get()
    HardwareRequestItem.objects.filter(pk=item.pk).update(requested_quantity=5, accepted_quantity=2)
    box = make_box(space)
    request.assigned_box = box
    request.save(update_fields=["assigned_box"])
    BoxScan.objects.create(makerspace=space, box=box, request=request, actor=admin, context=BoxScan.Context.ISSUE)
    evidence = make_issue_evidence(space, admin)
    monkeypatch.setattr("apps.evidence.storage.finalize_upload",
                        Mock(return_value=EvidenceValidationResult(size=10, content_type="image/png")))

    response = authenticated_client(admin).post(
        f"/api/v1/admin/requests/{request.pk}/issue", {"evidence_id": evidence.pk, "remark": "ok"}, format="json")

    assert response.status_code == 200
    item.refresh_from_db(); product.refresh_from_db()
    assert (item.requested_quantity, item.accepted_quantity, item.issued_quantity) == (5, 2, 2)
    assert (product.reserved_quantity, product.issued_quantity) == (0, 2)


def test_attached_issue_evidence_cannot_be_edited_or_deleted_through_the_orm(monkeypatch, settings):
    from apps.evidence.storage import EvidenceValidationResult
    settings.STORAGE_PRESIGN_METHOD = "post"
    space = make_space("m1-hr-immutable")
    admin = make_member("m1-hr-immutable-admin", space)
    product = make_product(space)
    request = make_accepted_request(space, product, 1)
    _reserve(product, 1, product.total_quantity)
    box = make_box(space)
    request.assigned_box = box
    request.save(update_fields=["assigned_box"])
    BoxScan.objects.create(makerspace=space, box=box, request=request, actor=admin, context=BoxScan.Context.ISSUE)
    evidence = make_issue_evidence(space, admin)
    monkeypatch.setattr("apps.evidence.storage.finalize_upload",
                        Mock(return_value=EvidenceValidationResult(size=10, content_type="image/png")))
    assert authenticated_client(admin).post(
        f"/api/v1/admin/requests/{request.pk}/issue", {"evidence_id": evidence.pk, "remark": "ok"},
        format="json").status_code == 200
    evidence.refresh_from_db()
    assert evidence.consumption_state == "consumed"
    key = evidence.object_key
    evidence.object_key = "evidence/tampered"
    with pytest.raises(Exception):
        evidence.save()
    with pytest.raises(Exception):
        evidence.delete()
    assert EvidencePhoto.objects.get(pk=evidence.pk).object_key == key

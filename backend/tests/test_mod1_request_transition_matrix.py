"""MOD-1: the request state machine as a full matrix over HTTP -- every action from every status.

The owning service (`hardware_requests/workflow.py`) allows only: accept/reject from pending_approval,
assign-box/issue from accepted, return from issued/partially_returned. Every other (status, action)
pair must answer a typed 409, change nothing (status, stock, scans) and write no audit row.
"""
import pytest

from apps.audit.models import AuditLog
from apps.boxes.models import BoxScan
from apps.hardware_requests.models import HardwareRequest
from tests.return_helpers import (
    authenticated_client, make_accepted_request, make_box, make_issue_evidence, make_member, make_product,
    make_return_evidence, make_space, make_user)
from apps.accounts.models import User

pytestmark = pytest.mark.django_db

S = HardwareRequest.Status
ALLOWED = {
    "accept": {S.PENDING_APPROVAL},
    "reject": {S.PENDING_APPROVAL},
    "assign-box": {S.ACCEPTED},
    "issue": {S.ACCEPTED},
    "return": {S.ISSUED, S.PARTIALLY_RETURNED},
}
ACTIONS = tuple(ALLOWED)


def _payload(action, space, admin, request):
    if action == "reject":
        return {"reason": "Not today."}
    if action == "assign-box":
        return {"box_code": make_box(space).code}
    if action == "issue":
        return {"evidence_id": make_issue_evidence(space, admin).pk, "remark": "Handed over."}
    if action == "return":
        item = request.items.get()
        return {"evidence_id": make_return_evidence(space, admin).pk, "box_code": "B-NONE", "remark": "Back.",
                "resolutions": [{"item_id": item.pk, "returned": 1, "damaged": 0, "missing": 0}]}
    return {}


@pytest.mark.parametrize("status", [s for s in S.values])
@pytest.mark.parametrize("action", ACTIONS)
def test_forbidden_transitions_are_refused_409_and_change_nothing(status, action):
    if status in {s.value for s in ALLOWED[action]}:
        pytest.skip("allowed pair; the happy paths are proven in test_issue/test_return_*/test_request_workflow")
    space = make_space(f"m1-tm-{action}-{status}".replace("_", "-"))
    admin = make_member(f"m1-tm-adm-{action}-{status}".replace("_", "-"), space)
    product = make_product(space, total_quantity=5, available_quantity=5)
    request = make_accepted_request(space, product, 1)
    HardwareRequest.objects.filter(pk=request.pk).update(status=status)
    product.refresh_from_db()
    stock_before = (product.available_quantity, product.reserved_quantity, product.issued_quantity)
    audits_before = AuditLog.objects.count()
    scans_before = BoxScan.objects.count()

    response = authenticated_client(admin).post(
        f"/api/v1/admin/requests/{request.pk}/{action}", _payload(action, space, admin, request), format="json")

    assert response.status_code == 409, (status, action, response.status_code, response.data)
    request.refresh_from_db(); product.refresh_from_db()
    assert request.status == status
    assert (product.available_quantity, product.reserved_quantity, product.issued_quantity) == stock_before
    assert AuditLog.objects.count() == audits_before and BoxScan.objects.count() == scans_before


def test_a_requester_or_signed_out_caller_cannot_drive_any_transition():
    space = make_space("m1-tm-roles")
    product = make_product(space)
    request = make_accepted_request(space, product, 1)
    HardwareRequest.objects.filter(pk=request.pk).update(status=S.PENDING_APPROVAL)
    requester = authenticated_client(request.requester)
    from rest_framework.test import APIClient
    for client in (requester, APIClient()):
        for action in ACTIONS:
            response = client.post(f"/api/v1/admin/requests/{request.pk}/{action}", {"reason": "x"}, format="json")
            assert response.status_code in (401, 403, 404), (action, response.status_code)
    request.refresh_from_db()
    assert request.status == S.PENDING_APPROVAL

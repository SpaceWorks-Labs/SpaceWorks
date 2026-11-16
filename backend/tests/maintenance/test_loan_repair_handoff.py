"""Item 5: a damaged return line handed off to repairs, and the loan's repair context."""

import pytest

from apps.audit.models import AuditLog
from apps.evidence.storage import EvidenceValidationResult
from apps.hardware_requests import workflow
from apps.hardware_requests.models import HardwareRequest, RequesterAccountability
from apps.maintenance.models import IssuePhoto, IssueReport, WorkOrder
from apps.maintenance.repairs import services_work as work
from tests.maintenance.l16_helpers import switch, world
from tests.return_helpers import authenticated_client, make_issued_request, make_member, make_return_evidence

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def quiet_storage(monkeypatch):
    monkeypatch.setattr("apps.evidence.storage.finalize_upload",
                        lambda evidence, max_bytes: EvidenceValidationResult(size=123, content_type="image/png"))


def damaged_return(w, *, remark="Cracked tip."):
    w.product.refresh_from_db()  # an earlier return moved counts in the DB; never save stale quantities
    request = make_issued_request(w.space, w.manager, [(w.product, 1)])
    evidence = make_return_evidence(w.space, w.manager)
    item = request.items.get()
    workflow.return_items(w.manager, request, evidence.pk, remark, request.assigned_box.code,
                          [{"item_id": item.pk, "returned": 0, "damaged": 1, "missing": 0}])
    return request, RequesterAccountability.objects.get(request=request), evidence


def url(w, request):
    return f"/api/v1/admin/makerspaces/{w.space.pk}/requests/{request.pk}/repairs"


def hand_off(user, w, request, line, **extra):
    return authenticated_client(user).post(url(w, request), {"accountability_id": line.pk, **extra}, format="json")


def test_inventory_manager_hands_a_damaged_line_off_to_repairs():
    w = world("lrh-ok")
    request, line, evidence = damaged_return(w)
    response = hand_off(w.im, w, request, line, note="Check the element too.")
    assert response.status_code == 201, response.content
    body = response.json()
    issue = IssueReport.objects.get(pk=body["issue_id"])
    assert (issue.source, issue.loan_id, issue.return_line_id, issue.area, issue.subject_type, issue.product_id) == (
        "loan", request.pk, line.pk, "inventory", "inventory_product", w.product.pk)
    assert issue.state == "triaged" and issue.reporter_id is None
    assert "Cracked tip." in issue.description and "Check the element too." in issue.description
    assert WorkOrder.objects.filter(pk=issue.work_order_id, subject_type="inventory_product").exists()
    audit = AuditLog.objects.get(action="repair.loan_handoff", makerspace=w.space)
    assert (audit.meta["accountability_id"], audit.meta["request_id"], audit.meta["evidence_id"]) == (
        line.pk, request.pk, evidence.pk)
    assert body["created"] is True and body["line"]["issue"]["work_order"]["id"] == issue.work_order_id
    assert body["line"]["remark"] == "Cracked tip."


def test_the_return_evidence_is_referenced_never_copied():
    w = world("lrh-ev")
    request, line, evidence = damaged_return(w)
    body = hand_off(w.manager, w, request, line).json()
    issue = IssueReport.objects.get(pk=body["issue_id"])
    assert IssuePhoto.objects.filter(issue=issue).count() == 0
    assert body["line"]["evidence_id"] == evidence.pk
    assert evidence.object_key not in str(body) and "url" not in body["line"]


def test_replaying_the_handoff_answers_the_same_issue():
    w = world("lrh-replay")
    request, line, _ = damaged_return(w)
    first = hand_off(w.im, w, request, line)
    again = hand_off(w.im, w, request, line)
    assert again.status_code == 200, again.content
    assert again.json()["created"] is False and again.json()["issue_id"] == first.json()["issue_id"]
    assert IssueReport.objects.filter(return_line=line).count() == 1
    assert AuditLog.objects.filter(action="repair.loan_handoff", makerspace=w.space).count() == 1
    assert WorkOrder.objects.filter(makerspace=w.space).count() == 1


def test_repairs_off_means_no_handoff_and_the_return_still_completes():
    w = world("lrh-off")
    switch(w.space, off=("inventory.repairs",))
    request, line, _ = damaged_return(w)
    request.refresh_from_db()
    assert request.status == HardwareRequest.Status.CLOSED_WITH_ISSUE
    client = authenticated_client(w.im)
    assert client.get(url(w, request)).status_code == 404
    refused = hand_off(w.im, w, request, line)
    assert refused.status_code == 404 and refused.json()["code"] == "capability_disabled"
    assert not IssueReport.objects.filter(makerspace=w.space).exists()


def test_wrong_role_wrong_space_and_wrong_loan_are_refused():
    w = world("lrh-deny")
    request, line, _ = damaged_return(w)
    refused = hand_off(w.tech, w, request, line)
    assert refused.status_code == 403 and refused.json()["code"] == "out_of_scope"
    assert authenticated_client(w.tech).get(url(w, request)).status_code == 403
    elsewhere = world("lrh-other")
    outsider = make_member("lrh-other-im", elsewhere.space, membership_role="inventory_manager")
    assert hand_off(outsider, w, request, line).status_code == 404
    assert authenticated_client(outsider).get(url(w, request)).status_code == 404
    other_request, _, _ = damaged_return(w)
    assert hand_off(w.im, w, other_request, line).status_code == 404
    assert not IssueReport.objects.filter(makerspace=w.space).exists()


def test_the_loan_shows_the_repairs_parts_to_buy_and_cost():
    w = world("lrh-ctx")
    request, line, _ = damaged_return(w)
    issue = IssueReport.objects.get(pk=hand_off(w.manager, w, request, line).json()["issue_id"])
    work.record_part(w.manager, issue, kind="needed", quantity=2, name="Heating element")
    work.quote(w.manager, issue, amount="18.50", currency="inr")
    body = authenticated_client(w.im).get(url(w, request)).json()
    [listed] = body["lines"]
    assert listed["accountability_id"] == line.pk and listed["issue"]["id"] == issue.pk
    assert [(part["kind"], part["name"], part["quantity"]) for part in listed["issue"]["parts"]] == [
        ("needed", "Heating element", 2)]
    assert [row["name"] for row in listed["issue"]["to_buy_items"]] == ["Heating element"]
    assert (listed["issue"]["quote_amount"], listed["issue"]["quote_currency"]) == ("18.50", "inr")

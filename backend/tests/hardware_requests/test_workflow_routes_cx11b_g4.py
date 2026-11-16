"""Real request transitions, reservations, evidence and audit across each surface gate."""
from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.boxes.models import BoxScan
from apps.evidence.storage import EvidenceValidationResult
from apps.hardware_requests import workflow
from apps.hardware_requests.models import HardwareRequest, HardwareRequestItem, ReturnEvent
from tests.accounts.account_factories import make_membership
from tests.modules.switch_matrix_object_helpers import object_world
from tests.operations.route_support_cx11b_g4 import cycle, outsider, send
from tests.return_helpers import make_issue_evidence, make_product, make_return_evidence

pytestmark = [pytest.mark.django_db, pytest.mark.area_lending]

NAMES = ["hardware_requests:request-accept", "hardware_requests:request-reject", "hardware_requests:request-assign-box", "hardware_requests:request-issue",
         "hardware_requests:request-return-due", "hardware_requests:request-return", "hardware_requests:guest-admin-request-return", "hardware_requests:staff-request-cancel"]


@pytest.mark.parametrize("native", [False, True], ids=["browser", "native"])
@pytest.mark.parametrize("gate", ["surface", "loans.enabled"])
@pytest.mark.parametrize("name", NAMES)
def test_request_command_changes_exact_domain_rows_and_restores(native, gate, name, monkeypatch):
    space, client, objects = object_world(native)
    actor = User.objects.get(username="sx-real-object-manager")
    make_membership(actor, space)
    product = make_product(space)
    row = HardwareRequest.objects.create(makerspace=space, requester=actor, requester_username=actor.username,
                                         requester_name="Retained borrower", status="pending_approval")
    item = HardwareRequestItem.objects.create(request=row, product=product, requested_quantity=2)
    box = objects["box"]
    due = timezone.now() + timedelta(days=4)
    body, audit = {}, ()
    surface = "guest_handover" if name.startswith("hardware_requests:guest-admin") else "request_workflow"
    key = surface if gate == "surface" else gate
    kwargs = {"pk": row.pk}
    if name == "hardware_requests:staff-request-cancel":
        kwargs["makerspace_id"] = space.pk
    if name not in {"hardware_requests:request-accept", "hardware_requests:request-reject"}:
        row = workflow.accept_request(actor, row)
    if name in {"hardware_requests:request-issue", "hardware_requests:request-return", "hardware_requests:guest-admin-request-return", "hardware_requests:request-return-due"}:
        row = workflow.assign_box(actor, row, box.code)
    finalized = EvidenceValidationResult(size=77, content_type="image/png")
    # Replace object storage's byte-validation port only; all evidence attachment and quantity services run.
    monkeypatch.setattr("apps.evidence.storage.finalize_upload", lambda evidence, limit: finalized)
    issue = make_issue_evidence(space, actor)
    if name in {"hardware_requests:request-return", "hardware_requests:guest-admin-request-return"}:
        row = workflow.issue_request(actor, row, issue.pk, "Issued complete")
    returned = make_return_evidence(space, actor)
    if name == "hardware_requests:request-accept":
        audit = ("request.accepted",)
    elif name == "hardware_requests:request-reject":
        body, audit = {"reason": "Unavailable for this project"}, ("request.rejected",)
    elif name == "hardware_requests:request-assign-box":
        body, audit = {"box_code": box.code}, ("box.assigned", "box.scanned")
    elif name == "hardware_requests:request-issue":
        body, audit = {"evidence_id": issue.pk, "remark": "Issued complete"}, ("evidence.attached", "request.issued")
    elif name == "hardware_requests:request-return-due":
        body, audit = {"return_due_at": due.isoformat()}, ("request.return_due_updated",)
    elif name == "hardware_requests:staff-request-cancel":
        body, audit = {"reason": "Project cancelled"}, ("request.cancelled",)
    else:
        body = {"evidence_id": returned.pk, "remark": "All parts returned", "box_code": box.code,
                "resolutions": [{"item_id": item.pk, "returned": 2}]}
        audit = ("request.returned", "evidence.attached", "box.scanned")
    url = reverse(name, kwargs=kwargs)

    def check(response):
        row.refresh_from_db()
        item.refresh_from_db()
        product.refresh_from_db()
        if name == "hardware_requests:request-accept":
            assert (row.status, row.accepted_by_id, item.accepted_quantity) == ("accepted", actor.pk, 2)
            assert (product.available_quantity, product.reserved_quantity, product.issued_quantity) == (8, 2, 0)
        elif name == "hardware_requests:request-reject":
            assert (row.status, row.rejection_reason) == ("rejected", body["reason"])
            assert (product.available_quantity, product.reserved_quantity) == (10, 0)
        elif name == "hardware_requests:request-assign-box":
            assert row.assigned_box_id == box.pk
            scan = BoxScan.objects.get(request=row)
            assert (scan.box_id, scan.actor_id, scan.context) == (box.pk, actor.pk, "issue")
        elif name == "hardware_requests:request-issue":
            assert (row.status, row.issue_evidence_id, row.issue_remark, item.issued_quantity) == ("issued", issue.pk, "Issued complete", 2)
            assert (product.available_quantity, product.reserved_quantity, product.issued_quantity) == (8, 0, 2)
            issue.refresh_from_db()
            assert issue.consumption_state == "consumed"
        elif name == "hardware_requests:request-return-due":
            assert row.return_due_at == due
        elif name == "hardware_requests:staff-request-cancel":
            assert (row.status, row.closed_by_id) == ("cancelled", actor.pk)
            assert (product.available_quantity, product.reserved_quantity) == (10, 0)
        else:
            assert (row.status, item.returned_quantity) == ("returned", 2)
            event = ReturnEvent.objects.get(request=row)
            assert (event.evidence_id, event.box_id, event.actor_id, event.remark) == (returned.pk, box.pk, actor.pk, "All parts returned")
            assert BoxScan.objects.filter(request=row, context="return").count() == 1
            assert (product.available_quantity, product.reserved_quantity, product.issued_quantity) == (10, 0, 0)
            returned.refresh_from_db()
            assert returned.consumption_state == "consumed"
    foreign = outsider(native)
    # Scoped object lookups: 520; maker-addressed cancellation: 481/494.
    cycle(space, key, lambda: send(client, "POST", url, body), check,
          foreign=lambda: send(foreign, "POST", url, body), foreign_native=native, audit=audit, refusal_key=surface)

"""Direct handout routes must issue and return real items with real evidence references."""
import pytest
from django.urls import reverse

from apps.hardware_requests.direct_loan_workflow import issue_direct_loan
from apps.hardware_requests.models import PublicToolLoan, ReturnEvent
from tests.hardware_requests.handout_support_cx11b_g4 import handout_world
from tests.operations.route_support_cx11b_g4 import contains, cycle, outsider, send

pytestmark = [pytest.mark.django_db, pytest.mark.area_lending]


@pytest.mark.parametrize("native", [False, True], ids=["browser", "native"])
@pytest.mark.parametrize("key", ["inventory.self_checkout", "loans.enabled"])
@pytest.mark.parametrize("name,method", [("hardware_requests:direct-loans", "GET"), ("hardware_requests:direct-loans", "POST"),
                                       ("hardware_requests:direct-loan-members", "GET"), ("hardware_requests:direct-loan-return", "POST")])
def test_direct_handout_method_proves_the_borrower_stock_and_evidence(native, key, name, method, monkeypatch):
    space, client, actor, product, issue, returned = handout_world(native, monkeypatch)
    loan = None
    if name == "hardware_requests:direct-loan-return" or name == "hardware_requests:direct-loans" and method == "GET":
        loan = issue_direct_loan(space, actor, borrower=actor, evidence_id=issue.pk, remark="Issued complete",
                                  qr_payloads=[], items=[{"product_id": product.pk, "quantity": 2}])
    kwargs = {"pk": loan.pk} if name == "hardware_requests:direct-loan-return" else {"makerspace_id": space.pk}
    url = reverse(name, kwargs=kwargs)
    body = {}
    if name == "hardware_requests:direct-loans" and method == "POST":
        body = {"borrower_id": actor.pk, "evidence_id": issue.pk, "remark": "Issued complete",
                "items": [{"product_id": product.pk, "quantity": 2}]}
    elif name == "hardware_requests:direct-loan-return":
        body = {"evidence_id": returned.pk, "notes": "All parts returned",
                "resolutions": [{"item_id": loan.request.items.get().pk, "returned": 2}]}

    def check(response):
        if name == "hardware_requests:direct-loan-members":
            assert [(row["user_id"], row["username"]) for row in response.data["results"]] == [(actor.pk, actor.username)]
        elif method == "GET":
            contains(response, loan.pk)
            assert response.data["results"][0]["request_id"] == loan.request_id
        elif name == "hardware_requests:direct-loans":
            created = PublicToolLoan.objects.get(pk=response.data["id"])
            assert (created.requester_id, created.status, created.source, created.request.issue_evidence_id) == (actor.pk, "checked_out", "admin_direct", issue.pk)
            assert (created.request.items.get().product_id, created.request.items.get().issued_quantity) == (product.pk, 2)
            product.refresh_from_db()
            assert (product.available_quantity, product.issued_quantity) == (8, 2)
            issue.refresh_from_db()
            assert issue.consumption_state == "consumed"
        else:
            loan.refresh_from_db()
            product.refresh_from_db()
            assert (loan.status, loan.return_evidence_id, loan.return_notes) == ("returned", returned.pk, "All parts returned")
            event = ReturnEvent.objects.get(request=loan.request)
            assert (event.evidence_id, event.actor_id, event.remark) == (returned.pk, actor.pk, "All parts returned")
            assert (product.available_quantity, product.issued_quantity) == (10, 0)
            returned.refresh_from_db()
            assert returned.consumption_state == "consumed"
    audit = () if method == "GET" else ("evidence.attached", "admin_direct.checked_out") if name == "hardware_requests:direct-loans" else ("admin_direct.returned", "evidence.attached")
    foreign = outsider(native)
    cycle(space, key, lambda: send(client, method, url, body), check,
          on=(201 if name == "hardware_requests:direct-loans" and method == "POST" else 200, None),
          off=(404, "feature_disabled"), refusal_key="inventory.self_checkout", audit=audit,
          foreign=lambda: send(foreign, method, url, body), foreign_native=native)
